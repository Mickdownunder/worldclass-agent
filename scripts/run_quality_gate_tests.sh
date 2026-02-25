#!/usr/bin/env bash
# Run Research Quality Guardrails red-team tests. Exit code = test exit code.
# CI / release blocker: must pass (exit 0) for build/run to succeed.
# Usage: from repo root, ./scripts/run_quality_gate_tests.sh
set -euo pipefail
ROOT="${OPERATOR_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"
python3 tests/research/test_quality_gates.py
