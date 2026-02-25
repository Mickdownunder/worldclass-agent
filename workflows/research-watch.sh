#!/usr/bin/env bash
# For all done research projects with watch enabled, check for updates and optionally notify.
# Usage: research-watch.sh
# Use from cron or run-scheduled-research.sh (e.g. weekly).
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
TOOLS="$OPERATOR_ROOT/tools"
RESEARCH="$OPERATOR_ROOT/research"

for dir in "$RESEARCH"/proj-*/; do
  [ -d "$dir" ] || continue
  project_id=$(basename "$dir")
  project_json="$dir/project.json"
  [ -f "$project_json" ] || continue

  status=$(python3 -c "
import json
try:
  d = json.load(open('$project_json'))
  print(d.get('status', ''), end='')
except Exception:
  print('', end='')
" 2>/dev/null || true)
  watch_enabled=$(python3 -c "
import json
try:
  d = json.load(open('$project_json'))
  w = d.get('watch') or {}
  print('true' if w.get('enabled') else 'false', end='')
except Exception:
  print('false', end='')
" 2>/dev/null || true)

  if [ "$status" != "done" ] || [ "$watch_enabled" != "true" ]; then
    continue
  fi

  # Optional: respect interval_hours (skip if last_checked within interval)
  run_check=1
  if python3 -c "
import json
from datetime import datetime, timezone, timedelta
try:
  d = json.load(open('$project_json'))
  w = d.get('watch') or {}
  last = w.get('last_checked')
  hours = w.get('interval_hours', 168)
  if last:
    dt = datetime.fromisoformat(last.replace('Z', '+00:00'))
    if datetime.now(timezone.utc) - dt < timedelta(hours=hours):
      exit(1)
except Exception:
  pass
exit(0)
" 2>/dev/null; then
    run_check=1
  else
    run_check=0
  fi
  [ "$run_check" -eq 0 ] && continue

  echo "[$(date -Iseconds)] Watch check: $project_id"
  result=$(python3 "$TOOLS/research_watch.py" check "$project_id" 2>/dev/null || echo '{"needs_update":false}')
  needs=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print('1' if d.get('needs_update') else '0', end='')" 2>/dev/null || echo "0")
  if [ "$needs" = "1" ]; then
    echo "[$(date -Iseconds)] Updates for $project_id — generating briefing"
    briefing=$(python3 "$TOOLS/research_watch.py" briefing "$project_id" 2>/dev/null || echo "")
    if [ -n "$briefing" ] && [ -x "$TOOLS/send-telegram.sh" ]; then
      MSG_FILE=$(mktemp)
      printf "Research update: %s\n\n%s" "$project_id" "$briefing" >> "$MSG_FILE"
      "$TOOLS/send-telegram.sh" "$MSG_FILE" 2>/dev/null || true
      rm -f "$MSG_FILE"
    fi
  fi
done

echo "[$(date -Iseconds)] Watch pass complete"
