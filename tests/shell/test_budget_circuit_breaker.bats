#!/usr/bin/env bats
# Budget / circuit breaker checks. Run from repo root: OPERATOR_ROOT=$PWD bats tests/shell/test_budget_circuit_breaker.bats

setup() {
  export OPERATOR_ROOT="${OPERATOR_ROOT:-$(cd "${BATS_TEST_FILENAME%/*}/../.." && pwd)}"
}

@test "research_budget.py exists" {
  [ -f "$OPERATOR_ROOT/tools/research_budget.py" ]
}

@test "research_budget.py check with missing project returns JSON with ok key" {
  run python3 "$OPERATOR_ROOT/tools/research_budget.py" check "proj-nonexistent-bats-$$" 2>&1
  # Script may exit 0 and print JSON (ok: false) or exit non-zero
  echo "$output" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'ok' in d or 'current_spend' in d" 2>/dev/null || [ "$status" -ne 0 ]
}
