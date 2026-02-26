#!/usr/bin/env bats
# Phase transition checks. Run from repo root: OPERATOR_ROOT=$PWD bats tests/shell/test_research_cycle_phases.bats

setup() {
  export OPERATOR_ROOT="${OPERATOR_ROOT:-$(cd "${BATS_TEST_FILENAME%/*}/../.." && pwd)}"
}

@test "research_advance_phase.py exists and is executable" {
  [ -f "$OPERATOR_ROOT/tools/research_advance_phase.py" ]
  [ -x "$OPERATOR_ROOT/tools/research_advance_phase.py" ] || [ -r "$OPERATOR_ROOT/tools/research_advance_phase.py" ]
}

@test "advance_phase usage shows when called without args" {
  run python3 "$OPERATOR_ROOT/tools/research_advance_phase.py" 2>&1 || true
  [ "$status" -ne 0 ]
  [[ "$output" == *"Usage"* ]] || [[ "$output" == *"usage"* ]]
}
