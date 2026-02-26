#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

cat > "$ART/product-spec.md" <<EOF
# Product Spec

Operator dashboard: Next.js UI (research, audit, jobs). No separate FastAPI app.
EOF
