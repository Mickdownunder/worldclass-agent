#!/usr/bin/env bash
# Run one research-cycle for every project that is not yet "done".
# Use with cron for autonomous multi-project research (e.g. every 6h).
# Usage: run-scheduled-research.sh
# Cron example: 0 */6 * * * /root/operator/tools/run-scheduled-research.sh >> /root/operator/logs/scheduled-research.log 2>&1
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
OP="$OPERATOR_ROOT/bin/op"
RESEARCH_DIR="$OPERATOR_ROOT/research"
LOG_DIR="$OPERATOR_ROOT/logs"

mkdir -p "$LOG_DIR"

for dir in "$RESEARCH_DIR"/proj-*/; do
  [ -d "$dir" ] || continue
  project_id=$(basename "$dir")
  project_json="$dir/project.json"
  [ -f "$project_json" ] || continue

  phase=$(python3 -c "
import json
try:
    d = json.load(open('$project_json'))
    print(d.get('phase', ''), end='')
except Exception:
    print('', end='')
" 2>/dev/null || true)

  if [ "$phase" = "done" ]; then
    echo "[$(date -Iseconds)] Skip $project_id (done)"
    continue
  fi

  echo "[$(date -Iseconds)] Run cycle for $project_id (phase: $phase)"
  job_dir=$("$OP" job new --workflow research-cycle --request "$project_id")
  "$OP" run "$job_dir" --timeout 300
  echo "[$(date -Iseconds)] Done $project_id"
done

# Watch mode: check done projects with watch.enabled (e.g. weekly via interval_hours)
WORKFLOWS_DIR="${OPERATOR_ROOT:-/root/operator}/workflows"
if [ -x "$WORKFLOWS_DIR/research-watch.sh" ]; then
  echo "[$(date -Iseconds)] Running research watch pass"
  "$WORKFLOWS_DIR/research-watch.sh" || true
fi
