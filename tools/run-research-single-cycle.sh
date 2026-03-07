#!/usr/bin/env bash
# Run exactly one research-phase job for a project.
# Usage: run-research-single-cycle.sh <project_id>
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
OP="$OPERATOR_ROOT/bin/op"
PROJECT_ID="${1:-}"

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 <project_id>" >&2
  exit 2
fi

if ! printf '%s' "$PROJECT_ID" | grep -Eq '^proj-[A-Za-z0-9_-]+$'; then
  echo "project_id must match proj-*" >&2
  exit 2
fi

if [ ! -d "$OPERATOR_ROOT/research/$PROJECT_ID" ]; then
  echo "Project not found: $PROJECT_ID" >&2
  exit 1
fi

phase=$(python3 -c "import json; d=json.load(open('$OPERATOR_ROOT/research/$PROJECT_ID/project.json')); print(d.get('phase',''), end='')")
status=$(python3 -c "import json; d=json.load(open('$OPERATOR_ROOT/research/$PROJECT_ID/project.json')); print(d.get('status',''), end='')")

case "$status" in
  done)
    echo "Project $PROJECT_ID is done."
    exit 0
    ;;
  pending_review)
    echo "Project $PROJECT_ID reached manual review gate: $status (phase: $phase)." 
    exit 0
    ;;
  failed*|cancelled|error|abandoned|aem_blocked)
    echo "Project $PROJECT_ID reached terminal failure status: $status (phase: $phase)." >&2
    exit 1
    ;;
esac

SYNTHESIZE_TIMEOUT=5400
if [ "$phase" = "synthesize" ]; then
  job_dir=$($OP job new --workflow research-phase --request "$PROJECT_ID" --timeout "$SYNTHESIZE_TIMEOUT")
else
  job_dir=$($OP job new --workflow research-phase --request "$PROJECT_ID")
fi

run_exit=0
$OP run "$job_dir" || run_exit=$?

echo "PROJECT_ID=$PROJECT_ID"
echo "JOB_DIR=$job_dir"
echo "PHASE=$phase"
echo "STATUS=$status"
echo "RUN_EXIT=$run_exit"

exit "$run_exit"
