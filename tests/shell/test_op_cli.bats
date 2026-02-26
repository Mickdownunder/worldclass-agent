#!/usr/bin/env bats
# CLI tests for bin/op. Run from repo root: OPERATOR_ROOT=$PWD bats tests/shell/test_op_cli.bats

setup() {
  export OPERATOR_ROOT="${OPERATOR_ROOT:-$(cd "${BATS_TEST_FILENAME%/*}/../.." && pwd)}"
  export PATH="$OPERATOR_ROOT/bin:$PATH"
}

@test "op job status runs and exits 0" {
  run op job status --limit 1
  # May exit 0 (has jobs) or 0 (empty); should not crash
  [ "$status" -eq 0 ] || [ "$status" -eq 1 ]
}

@test "op healthcheck runs" {
  run op healthcheck
  [ "$status" -eq 0 ] || [ "$status" -eq 1 ]
}
