#!/usr/bin/env bash
# Run one research cycle every N hours until phase is "done" or MAX_DAYS reached.
# Usage: run-research-over-days.sh <project_id> [sleep_hours] [max_days]
# Example: ./run-research-over-days.sh proj-20260225-654f85b2 6 14
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
OP="$OPERATOR_ROOT/bin/op"
PROJECT_ID="${1:-}"
SLEEP_HOURS="${2:-6}"
MAX_DAYS="${3:-14}"

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 <project_id> [sleep_hours=6] [max_days=14]"
  echo "Example: $0 proj-20260225-654f85b2 6 14"
  exit 2
fi

if [ ! -d "$OPERATOR_ROOT/research/$PROJECT_ID" ]; then
  echo "Project not found: $PROJECT_ID"
  exit 1
fi

LOG="$OPERATOR_ROOT/research/$PROJECT_ID/over-days.log"
START_TS=$(date +%s)
MAX_TS=$((START_TS + MAX_DAYS * 86400))
run=0

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

while true; do
  phase=$(python3 -c "import json; d=json.load(open('$OPERATOR_ROOT/research/$PROJECT_ID/project.json')); print(d.get('phase',''), end='')" 2>/dev/null || echo "")
  if [ "$phase" = "done" ]; then
    log "Project $PROJECT_ID is done."
    ls -la "$OPERATOR_ROOT/research/$PROJECT_ID/reports/" 2>/dev/null || true
    exit 0
  fi

  now=$(date +%s)
  if [ "$now" -ge "$MAX_TS" ]; then
    log "Stopped after $MAX_DAYS days. Phase: $phase"
    exit 0
  fi

  run=$((run + 1))
  log "[Run $run] Phase: $phase — starting cycle..."
  job_dir=$($OP job new --workflow research-cycle --request "$PROJECT_ID")
  $OP run "$job_dir" --timeout 300
  log "[Run $run] Done. Next run in ${SLEEP_HOURS}h."

  sleep $((SLEEP_HOURS * 3600))
done
