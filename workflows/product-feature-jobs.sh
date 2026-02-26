#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

# Job list / delete: use Next.js UI (Audit area). No separate FastAPI dashboard.
cat > "$ART/product-feature.md" <<EOF
# Product Feature

Feature: job list and delete — available in Next.js UI (Audit).
EOF
