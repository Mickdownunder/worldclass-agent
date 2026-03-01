#!/usr/bin/env bash
# Build and start the Operator UI in production mode.
# Usage:
#   OPERATOR_ROOT=/root/operator ./scripts/run-ui-production.sh
#   OPERATOR_ROOT=/root/operator ./scripts/run-ui-production.sh --build-only
#   PORT=3001 ./scripts/run-ui-production.sh
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
UI_DIR="$OPERATOR_ROOT/ui"
PORT="${PORT:-3000}"

if [ ! -d "$UI_DIR" ]; then
  echo "UI directory not found: $UI_DIR" >&2
  exit 1
fi

cd "$UI_DIR"

if [ "${1:-}" = "--build-only" ]; then
  npm ci
  npm run build
  echo "Build done. Start with: cd $UI_DIR && PORT=$PORT npm run start"
  exit 0
fi

if [ ! -d ".next" ] || [ ! -f ".next/BUILD_ID" ]; then
  echo "No production build found. Running build first..."
  npm ci
  npm run build
fi

export PORT
exec npm run start
