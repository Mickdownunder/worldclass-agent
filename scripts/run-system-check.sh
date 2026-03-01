#!/usr/bin/env bash
# System-Check: Prüft Health, Jobs, Research-Ordner, Memory-DB, Sandbox.
# Usage: ./scripts/run-system-check.sh [OPERATOR_ROOT]
# Exit: 0 wenn alles OK, 1 wenn ein Check fehlschlägt.
set -euo pipefail

OPERATOR_ROOT="${1:-${OPERATOR_ROOT:-/root/operator}}"
cd "$OPERATOR_ROOT"
FAIL=0

echo "=== System-Check $OPERATOR_ROOT ==="

# 1. Health
if ./bin/op healthcheck 2>/dev/null | grep -q '"healthy":\s*true'; then
  echo "[OK] op healthcheck (healthy: true)"
else
  echo "[FAIL] op healthcheck"
  FAIL=1
fi

# 2. Jobs
if ./bin/op job status --limit 5 2>/dev/null | head -20 | grep -qE 'DONE|RUNNING|PENDING|id'; then
  echo "[OK] op job status"
else
  echo "[FAIL] op job status"
  FAIL=1
fi

# 3. Research-Ordner
if [ -d "research" ]; then
  echo "[OK] research/ vorhanden"
else
  echo "[FAIL] research/ fehlt"
  FAIL=1
fi

# 4. Memory-DB
if python3 -c "
import sys
sys.path.insert(0, r\"$OPERATOR_ROOT\")
from lib.memory import Memory
m = Memory()
s = m.state_summary()
print(s['totals']['episodes'], s['totals'].get('avg_quality', 0))
m.close()
" 2>/dev/null | grep -qE '^[0-9]'; then
  echo "[OK] Memory-DB"
else
  echo "[FAIL] Memory-DB"
  FAIL=1
fi

# 5. Sandbox (Docker)
if docker run --rm python:3.11-slim python -c "print(1)" 2>/dev/null | grep -q 1; then
  echo "[OK] Sandbox (Docker python:3.11-slim)"
else
  echo "[FAIL] Sandbox (Docker)"
  FAIL=1
fi

echo "=== Ende ==="
exit $FAIL
