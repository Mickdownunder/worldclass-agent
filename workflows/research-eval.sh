#!/usr/bin/env bash
# Run offline scorecard for research projects (continuous eval).
# Usage: research-eval.sh [project_id]
#   No args: evaluate all projects that have verify/ or reports/
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
TOOLS="$OPERATOR_ROOT/tools"
RESEARCH="$OPERATOR_ROOT/research"

if [ -n "${1:-}" ]; then
  python3 "$TOOLS/research_eval.py" "$1"
else
  python3 "$TOOLS/research_eval.py" --all
fi
