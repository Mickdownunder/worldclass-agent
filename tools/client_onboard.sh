#!/usr/bin/env bash
set -euo pipefail

# Onboard a new client. Creates config, validates, runs test pack.
#
# Usage:
#   client_onboard.sh <client_id> <client_name> <niche> <topics_csv> <telegram_chat_id> [min_score]
#
# Example:
#   client_onboard.sh acme "Acme Corp" "B2B SaaS" "growth,pricing,churn" "123456789" 0.6

CLIENTS_DIR="/root/operator/factory/clients"
SCHEMA="/root/operator/conf/schemas/client.schema.json"
TOOLS="/root/operator/tools"

if [[ $# -lt 5 ]]; then
  echo "Usage: client_onboard.sh <id> <name> <niche> <topics_csv> <chat_id> [min_score]" >&2
  echo "" >&2
  echo "Example:" >&2
  echo "  client_onboard.sh acme 'Acme Corp' 'B2B SaaS' 'growth,pricing,churn' '123456789' 0.6" >&2
  exit 2
fi

CLIENT_ID="$1"
CLIENT_NAME="$2"
NICHE="$3"
TOPICS_CSV="$4"
CHAT_ID="$5"
MIN_SCORE="${6:-0.6}"

CONFIG="$CLIENTS_DIR/$CLIENT_ID.json"

if [[ -f "$CONFIG" ]]; then
  echo "ERROR: client config already exists: $CONFIG" >&2
  echo "To update, edit the file directly." >&2
  exit 1
fi

# Build topics JSON array
IFS=',' read -ra TOPICS_ARR <<< "$TOPICS_CSV"
TOPICS_JSON=$(printf '%s\n' "${TOPICS_ARR[@]}" | jq -R . | jq -sc .)

mkdir -p "$CLIENTS_DIR"

cat > "$CONFIG" <<EOF
{
  "id": "$CLIENT_ID",
  "name": "$CLIENT_NAME",
  "niche": "$NICHE",
  "topics": $TOPICS_JSON,
  "min_score": $MIN_SCORE,
  "max_items_per_pack": 10,
  "delivery": {
    "type": "telegram",
    "telegram_chat_id": "$CHAT_ID"
  }
}
EOF

echo "Created: $CONFIG"
cat "$CONFIG"

# Validate against schema
if [[ -f "$SCHEMA" ]]; then
  echo ""
  echo "Validating against schema..."
  if python3 "$TOOLS/schema_validate.py" "$SCHEMA" "$CONFIG"; then
    echo "Schema validation: PASSED"
  else
    echo "Schema validation: FAILED — config may have issues" >&2
    exit 1
  fi
fi

echo ""
echo "Client '$CLIENT_NAME' ($CLIENT_ID) onboarded successfully."
echo ""
echo "Next steps:"
echo "  1. Run factory cycle:  /factory  (via Telegram)"
echo "  2. Or manually:        /root/operator/bin/op job new --workflow factory-cycle --request 'run for $CLIENT_ID' | xargs -I{} /root/operator/bin/op run {}"
echo "  3. Check packs:        ls /root/operator/factory/packs/$CLIENT_ID/"
