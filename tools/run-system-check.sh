#!/usr/bin/env bash
# Quick system check: function + quality signals.
# Usage: ./tools/run-system-check.sh
# Exit 0 = all passed, 1 = at least one failed.
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
OP="$OPERATOR_ROOT/bin/op"
FAIL=0

check() {
  if "$@"; then
    echo "OK   $*"
  else
    echo "FAIL $*"
    FAIL=1
  fi
}

cd "$OPERATOR_ROOT"

echo "=== A) Function ==="
check "$OP" healthcheck >/dev/null 2>&1
check test -d research
check test -d workflows

echo ""
echo "=== B) Quality signals ==="
# Jobs: not only failures
if "$OP" job status --limit 10 2>/dev/null | grep -q "FAILED" && ! "$OP" job status --limit 10 2>/dev/null | grep -q "DONE"; then
  echo "FAIL Last jobs are only FAILED (no DONE)"
  FAIL=1
else
  echo "OK   Jobs: at least some DONE or mixed"
fi

# Memory reachable
if python3 -c "
from lib.memory import Memory
m = Memory()
s = m.state_summary()
assert 'totals' in s
m.close()
" 2>/dev/null; then
  echo "OK   Memory DB reachable"
else
  echo "FAIL Memory DB unreachable or error"
  FAIL=1
fi

# Research projects (optional: at least one with project.json)
COUNT=0
for d in research/proj-*/; do
  [ -f "${d}project.json" ] && COUNT=$((COUNT+1))
done
echo "     Research projects with project.json: $COUNT"

echo ""
if [ $FAIL -eq 0 ]; then
  echo "All checks passed."
else
  echo "One or more checks failed. See docs/SYSTEM_CHECK.md for details."
fi
exit $FAIL
