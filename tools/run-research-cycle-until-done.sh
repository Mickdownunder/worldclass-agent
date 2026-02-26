#!/usr/bin/env bash
# Run research-cycle repeatedly until project phase is "done".
# Usage: run-research-cycle-until-done.sh <project_id>
# Example: ./run-research-cycle-until-done.sh proj-20260225-654f85b2
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
OP="$OPERATOR_ROOT/bin/op"
PROJECT_ID="${1:-}"

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 <project_id>"
  echo "Example: $0 proj-20260225-654f85b2"
  exit 2
fi

if [ ! -d "$OPERATOR_ROOT/research/$PROJECT_ID" ]; then
  echo "Project not found: $PROJECT_ID"
  exit 1
fi

MAX_RUNS=10
run=0

while [ $run -lt $MAX_RUNS ]; do
  phase=$(python3 -c "import json; d=json.load(open('$OPERATOR_ROOT/research/$PROJECT_ID/project.json')); print(d.get('phase',''), end='')")
  if [ "$phase" = "done" ]; then
    echo "Project $PROJECT_ID is done."
    ls -la "$OPERATOR_ROOT/research/$PROJECT_ID/reports/" 2>/dev/null || true
    exit 0
  fi

  run=$((run + 1))
  echo "[Run $run] Phase: $phase — starting cycle job..."
  job_dir=$($OP job new --workflow research-cycle --request "$PROJECT_ID")
  $OP run "$job_dir" --timeout 900
  echo "[Run $run] Done."
done

echo "Stopped after $MAX_RUNS runs. Check project: $OPERATOR_ROOT/research/$PROJECT_ID/project.json"
exit 0
