#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

OUT=$(/root/operator/tools/infra-summary.sh)

echo "$OUT" > "$ART/tool-output.txt"
