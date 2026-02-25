#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

echo "# Infra status" > "$ART/report.md"
echo "" >> "$ART/report.md"
echo "Uptime:" >> "$ART/report.md"
uptime >> "$ART/report.md"
echo "" >> "$ART/report.md"
echo "Disk:" >> "$ART/report.md"
df -h >> "$ART/report.md"
