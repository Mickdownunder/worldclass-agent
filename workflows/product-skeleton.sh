#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

# Dashboard is the Next.js UI in ui/ — no separate operator-dashboard skeleton.
cat > "$ART/product-skeleton.md" <<EOF
# Product Skeleton

Dashboard: Next.js app in ui/
EOF
