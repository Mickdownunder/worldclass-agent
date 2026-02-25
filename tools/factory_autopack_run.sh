#!/usr/bin/env bash
set -euo pipefail

# Standalone autopack: match → pack → deliver for all clients.
# Used by factory-cycle.sh or can be called directly.

CLIENTS_DIR="/root/operator/factory/clients"
OPPS="/root/operator/factory/opportunities/opportunities.jsonl"
MAP="/root/operator/factory/opportunities/client_match_map.json"
PACKS_ROOT="/root/operator/factory/packs"
TOOLS="/root/operator/tools"

mkdir -p "$(dirname "$MAP")" "$PACKS_ROOT"

if [[ ! -f "$OPPS" ]]; then
  echo "ERROR: missing opportunities file: $OPPS" >&2
  exit 1
fi

if [[ ! -d "$CLIENTS_DIR" ]] || [[ -z "$(ls "$CLIENTS_DIR"/*.json 2>/dev/null)" ]]; then
  echo "ERROR: no client configs in $CLIENTS_DIR" >&2
  exit 1
fi

echo "Matching opportunities to clients..."
python3 "$TOOLS/opportunity_match_clients.py" "$CLIENTS_DIR" "$OPPS" "$MAP"

DELIVERED=0

for cfile in "$CLIENTS_DIR"/*.json; do
  cid="$(jq -r .id "$cfile")"
  chat_id="$(jq -r '.delivery.telegram_chat_id // empty' "$cfile")"

  pack_dir="$(python3 "$TOOLS/opportunity_pack_build.py" "$cid" "$MAP" "$PACKS_ROOT" 2>&1 || true)"

  if [[ -n "$pack_dir" ]] && [[ -d "$pack_dir" ]]; then
    echo "PACK_BUILT=$pack_dir ($cid)"

    if [[ -n "$chat_id" ]]; then
      if "$TOOLS/pack_deliver.sh" "$chat_id" "$pack_dir"; then
        DELIVERED=$((DELIVERED + 1))
      else
        echo "WARN: delivery failed for $cid" >&2
      fi
    else
      echo "SKIP: no chat_id for $cid"
    fi
  else
    echo "SKIP: no matches for $cid"
  fi
done

echo "Autopack complete. Delivered: $DELIVERED packs"
