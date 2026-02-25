#!/usr/bin/env bash
set -euo pipefail

# Factory Cycle: Discover → Match → Pack → Deliver
# This is the client-facing opportunity pipeline.

ART="$PWD/artifacts"
mkdir -p "$ART"

TOOLS="/root/operator/tools"
FACTORY="/root/operator/factory"
CLIENTS_DIR="$FACTORY/clients"
OPPS_FILE="$FACTORY/opportunities/opportunities.jsonl"
MATCH_MAP="$FACTORY/opportunities/client_match_map.json"
PACKS_ROOT="$FACTORY/packs"

mkdir -p "$FACTORY/opportunities" "$PACKS_ROOT"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$PWD/log.txt"; echo "$*" >&2; }

# ---------------------------------------------------------------------------
# Step 1: Discover opportunities from real sources
# ---------------------------------------------------------------------------
log "STEP 1: Discovering opportunities..."

SECRETS="/root/operator/conf/secrets.env"
if [ -f "$SECRETS" ]; then
  set -a
  source "$SECRETS"
  set +a
fi

NEW_OPPS="$ART/discovered.jsonl"
if python3 "$TOOLS/opportunity_discover.py" "$CLIENTS_DIR" --max-items 20 > "$NEW_OPPS" 2>> "$PWD/log.txt"; then
  NEW_COUNT=$(wc -l < "$NEW_OPPS" | tr -d ' ')
  log "Discovered $NEW_COUNT new opportunities"
else
  log "WARN: Discovery had issues, continuing with existing data"
  NEW_COUNT=0
fi

# ---------------------------------------------------------------------------
# Step 2: Append new opportunities to the master file (deduplicate by title)
# ---------------------------------------------------------------------------
log "STEP 2: Ingesting opportunities..."

if [ "$NEW_COUNT" -gt 0 ] 2>/dev/null; then
  python3 - "$NEW_OPPS" "$OPPS_FILE" <<'PY'
import json, sys
from pathlib import Path

new_path, master_path = sys.argv[1], sys.argv[2]

existing_titles = set()
master = Path(master_path)
if master.exists():
    for line in master.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            existing_titles.add(json.loads(line).get("title", "").lower())
        except json.JSONDecodeError:
            pass

added = 0
with open(master_path, "a") as f:
    for line in Path(new_path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            opp = json.loads(line)
            title = opp.get("title", "").lower()
            if title and title not in existing_titles:
                f.write(json.dumps(opp, ensure_ascii=False) + "\n")
                existing_titles.add(title)
                added += 1
        except json.JSONDecodeError:
            pass

print(f"Ingested {added} new (deduplicated) opportunities")
PY
fi

TOTAL=$(wc -l < "$OPPS_FILE" 2>/dev/null | tr -d ' ' || echo 0)
log "Total opportunities in master: $TOTAL"

# ---------------------------------------------------------------------------
# Step 3: Match opportunities to clients
# ---------------------------------------------------------------------------
log "STEP 3: Matching to clients..."

if [ ! -f "$OPPS_FILE" ] || [ "$TOTAL" -eq 0 ]; then
  log "No opportunities to match"
  echo "No opportunities available." > "$ART/result.md"
  exit 0
fi

python3 "$TOOLS/opportunity_match_clients.py" "$CLIENTS_DIR" "$OPPS_FILE" "$MATCH_MAP" >> "$PWD/log.txt" 2>&1 || true
cp "$MATCH_MAP" "$ART/client_match_map.json" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Step 4: Build packs per client
# ---------------------------------------------------------------------------
log "STEP 4: Building packs..."

RESULT="$ART/result.md"
echo "# Factory Cycle Result — $(date -u +%Y-%m-%d)" > "$RESULT"
echo "" >> "$RESULT"

DELIVERED=0
for cfile in "$CLIENTS_DIR"/*.json; do
  CID="$(jq -r .id "$cfile")"
  CNAME="$(jq -r .name "$cfile")"
  CHAT_ID="$(jq -r '.delivery.telegram_chat_id // empty' "$cfile")"

  log "Building pack for $CID ($CNAME)..."

  PACK_DIR=$(python3 "$TOOLS/opportunity_pack_build.py" "$CID" "$MATCH_MAP" "$PACKS_ROOT" 2>> "$PWD/log.txt" || true)

  if [ -n "$PACK_DIR" ] && [ -d "$PACK_DIR" ]; then
    echo "## $CNAME" >> "$RESULT"
    ITEMS=$(jq -r .items "$PACK_DIR/pack.json" 2>/dev/null || echo 0)
    echo "- Pack: $PACK_DIR" >> "$RESULT"
    echo "- Items: $ITEMS" >> "$RESULT"
    echo "" >> "$RESULT"

    # ---------------------------------------------------------------------------
    # Step 5: Deliver via Telegram
    # ---------------------------------------------------------------------------
    if [ -n "$CHAT_ID" ] && [ "$ITEMS" -gt 0 ] 2>/dev/null; then
      log "Delivering to $CID (chat $CHAT_ID)..."

      if "$TOOLS/pack_deliver.sh" "$CHAT_ID" "$PACK_DIR" >> "$PWD/log.txt" 2>&1; then
        echo "- Delivery: SENT to Telegram" >> "$RESULT"
        DELIVERED=$((DELIVERED + 1))
      else
        echo "- Delivery: FAILED" >> "$RESULT"
        log "WARN: Delivery failed for $CID"
      fi
    else
      echo "- Delivery: skipped (no chat_id or no items)" >> "$RESULT"
    fi
    echo "" >> "$RESULT"
  else
    echo "## $CNAME" >> "$RESULT"
    echo "- No matching opportunities" >> "$RESULT"
    echo "" >> "$RESULT"
  fi
done

log "Factory cycle complete. Delivered: $DELIVERED packs"
echo "Delivered: $DELIVERED packs" >> "$RESULT"

# Create telegram notification
{
  echo "Factory cycle complete"
  echo ""
  echo "Discovered: ${NEW_COUNT:-0} new opportunities"
  echo "Total in database: $TOTAL"
  echo "Packs delivered: $DELIVERED"
  echo ""
  head -n 30 "$RESULT"
} > "$ART/telegram.txt"
