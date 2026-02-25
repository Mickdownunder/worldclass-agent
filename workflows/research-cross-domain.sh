#!/usr/bin/env bash
# Index all research findings with embeddings, then find cross-domain links.
# Optionally notify via Telegram when new insights are found.
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
TOOLS="$OPERATOR_ROOT/tools"
ART="$PWD/artifacts"
mkdir -p "$ART"

SECRETS="$OPERATOR_ROOT/conf/secrets.env"
[ -f "$SECRETS" ] && set -a && source "$SECRETS" && set +a

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Indexing findings with embeddings..." >> "$PWD/log.txt"
python3 "$TOOLS/research_embed.py" >> "$PWD/log.txt" 2>&1 || true

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Running cross-domain discovery..." >> "$PWD/log.txt"
python3 "$TOOLS/research_cross_domain.py" --threshold 0.75 --max-pairs 20 > "$ART/cross_domain.json" 2>> "$PWD/log.txt" || true

if [ -f "$ART/cross_domain.json" ]; then
  count=$(python3 -c "import json; d=json.load(open('$ART/cross_domain.json')); print(d.get('count',0), end='')")
  if [ "${count:-0}" -gt 0 ]; then
    echo "Cross-domain insights: $count" >> "$PWD/log.txt"
    if [ -f "$OPERATOR_ROOT/tools/send-telegram.sh" ] && [ -n "${UI_TELEGRAM_NOTIFY:-}" ]; then
      msg="Research: $count cross-domain insight(s) found. Check dashboard."
      "$OPERATOR_ROOT/tools/send-telegram.sh" "$msg" >> "$PWD/log.txt" 2>&1 || true
    fi
  fi
fi

echo "done"
