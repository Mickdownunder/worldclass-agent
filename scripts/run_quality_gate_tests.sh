#!/usr/bin/env bash
# Run full test suite (pytest) with coverage. Exit code = test exit code.
# CI / release blocker: must pass (exit 0) for build/run to succeed.
# Usage: from repo root, ./scripts/run_quality_gate_tests.sh
# Coverage: lib + tools, report in term + xml (CI artifact). Schwellwert siehe --cov-fail-under.
set -euo pipefail
ROOT="${OPERATOR_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"
python3 -m pytest tests/ -v --tb=short \
  --cov=lib --cov=tools --no-cov-on-fail \
  --cov-report=term \
  --cov-report=xml:coverage.xml \
  --cov-fail-under=70
