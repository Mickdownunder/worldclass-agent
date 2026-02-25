#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

BASE="/root/operator/sandbox/products/operator-dashboard"

cat > "$BASE/spec.md" <<EOF
# Operator Dashboard Spec

## Purpose
Visualize operator system activity.

## Features
- job list
- artifact browsing
- tool registry view
- goal progress view

## Constraints
- read-only
- file-system backed
- no database
EOF

cat > "$ART/product-spec.md" <<EOF
# Product Spec Created

Location: $BASE/spec.md
EOF
