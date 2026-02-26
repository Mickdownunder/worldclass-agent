#!/usr/bin/env bats
# Tests for research-init workflow. Run from repo root: OPERATOR_ROOT=$PWD bats tests/shell/test_research_init.bats

setup() {
  export OPERATOR_ROOT="${OPERATOR_ROOT:-$(cd "${BATS_TEST_FILENAME%/*}/../.." && pwd)}"
  export RESEARCH_ROOT="$OPERATOR_ROOT/research"
  test_proj="$BATS_TEST_TMPDIR/proj-bats-test-$$"
  mkdir -p "$test_proj"
}

teardown() {
  rm -rf "$test_proj" 2>/dev/null || true
}

@test "research-init.sh creates project.json when given question" {
  skip "Requires workflows/research-init.sh to accept args; adjust when workflow is script-callable"
  # Placeholder: when research-init is invokable with question, assert project.json exists
  [ -d "$OPERATOR_ROOT/workflows" ]
}
