#!/usr/bin/env bash
# Run the research orchestrator (June-level: decide next research + sandbox from done reports).
# Usage: run-research-orchestrator.sh [--dry-run]
# Cron example (e.g. every 2 hours): 0 */2 * * * /root/operator/tools/run-research-orchestrator.sh >> /root/operator/logs/orchestrator.log 2>&1
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
LOG_DIR="${OPERATOR_ROOT}/logs"
mkdir -p "$LOG_DIR"

# Load secrets so OPENAI_API_KEY (and optional Gemini) are set
if [ -f "$OPERATOR_ROOT/conf/secrets.env" ]; then
  set +u
  source "$OPERATOR_ROOT/conf/secrets.env" 2>/dev/null || true
  set -u
fi

export OPERATOR_ROOT
exec python3 "$OPERATOR_ROOT/tools/research_orchestrator.py" "$@"
