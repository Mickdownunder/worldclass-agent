#!/usr/bin/env bash
set -euo pipefail

# Deliver an opportunity pack to a Telegram chat.
# Usage: pack_deliver.sh <chat_id> <pack_dir>

CHAT_ID="${1:?chat_id required}"
PACK_DIR="${2:?pack_dir required}"
TOOLS_DIR="$(dirname "$0")"

SUMMARY="$PACK_DIR/summary.md"
PACK_META="$PACK_DIR/pack.json"

if [[ ! -f "$SUMMARY" ]]; then
  echo "ERROR: missing summary: $SUMMARY" >&2
  exit 1
fi

CLIENT_NAME=""
ITEMS=0
if [[ -f "$PACK_META" ]]; then
  CLIENT_NAME="$(jq -r '.client_name // ""' "$PACK_META" 2>/dev/null || true)"
  ITEMS="$(jq -r '.items // 0' "$PACK_META" 2>/dev/null || true)"
fi

MSG=$(mktemp /tmp/pack-deliver-XXXXXX.txt)
trap 'rm -f "$MSG"' EXIT

{
  echo "📦 Opportunity Pack"
  if [[ -n "$CLIENT_NAME" ]]; then
    echo "Client: $CLIENT_NAME"
  fi
  echo "Items: $ITEMS"
  echo "Date: $(date -u +%Y-%m-%d)"
  echo ""
  head -n 50 "$SUMMARY"
  if [[ $(wc -l < "$SUMMARY") -gt 50 ]]; then
    echo ""
    echo "... (full pack: $PACK_DIR)"
  fi
} > "$MSG"

export TELEGRAM_TARGET="$CHAT_ID"
"$TOOLS_DIR/send-telegram.sh" "$MSG" "$CHAT_ID"

echo "DELIVERED $PACK_DIR → $CHAT_ID"
