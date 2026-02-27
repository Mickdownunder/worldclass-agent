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
MAX_SAME_PHASE=2
run=0
last_phase=""
same_phase_count=0

while [ $run -lt $MAX_RUNS ]; do
  phase=$(python3 -c "import json; d=json.load(open('$OPERATOR_ROOT/research/$PROJECT_ID/project.json')); print(d.get('phase',''), end='')")
  status=$(python3 -c "import json; d=json.load(open('$OPERATOR_ROOT/research/$PROJECT_ID/project.json')); print(d.get('status',''), end='')")

  if [ "$phase" = "done" ]; then
    echo "Project $PROJECT_ID is done."
    ls -la "$OPERATOR_ROOT/research/$PROJECT_ID/reports/" 2>/dev/null || true
    exit 0
  fi

  case "$status" in
    failed*|cancelled|error|abandoned|aem_blocked|pending_review)
      echo "Project $PROJECT_ID reached terminal status: $status (phase: $phase). Stopping."
      exit 0
      ;;
  esac

  if [ "$phase" = "$last_phase" ]; then
    same_phase_count=$((same_phase_count + 1))
    if [ "$same_phase_count" -ge "$MAX_SAME_PHASE" ]; then
      echo "Phase '$phase' stuck after $same_phase_count retries without advancing. Stopping."
      exit 0
    fi
  else
    same_phase_count=0
  fi
  last_phase="$phase"

  run=$((run + 1))
  echo "[Run $run] Phase: $phase, Status: $status — starting cycle job..."
  job_dir=$($OP job new --workflow research-cycle --request "$PROJECT_ID")
  run_exit=0
  $OP run "$job_dir" --timeout 900 || run_exit=$?
  if [ "$run_exit" -ne 0 ]; then
    echo "[Run $run] Job exited with $run_exit — continuing next run (phase may have advanced)." >&2
  else
    echo "[Run $run] Done."
  fi
done

echo "Stopped after $MAX_RUNS runs. Check project: $OPERATOR_ROOT/research/$PROJECT_ID/project.json"
exit 0
