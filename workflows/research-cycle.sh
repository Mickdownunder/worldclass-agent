#!/usr/bin/env bash
set -euo pipefail
OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
PROJECT_ID="${1:-}"
if [ -f "job.json" ]; then
  REQUEST=$(python3 -c "import json; d=json.load(open('job.json')); print(d.get('request',''), end='')")
  PROJECT_ID=$(echo "${REQUEST:-$*}" | awk '{print $1}')
fi
if [ -z "$PROJECT_ID" ]; then
  echo "Usage: research-cycle.sh <project_id>" >&2
  exit 2
fi
exec bash "$OPERATOR_ROOT/tools/run-research-single-cycle.sh" "$PROJECT_ID"
