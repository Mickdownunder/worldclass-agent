#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

echo "{" > "$ART/signals.json"
echo "\"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"," >> "$ART/signals.json"
echo "\"disk_root_use\": \"$(df / | tail -1 | awk '{print $5}')\"," >> "$ART/signals.json"
echo "\"load\": \"$(uptime | awk -F'load average:' '{print $2}')\"" >> "$ART/signals.json"
echo "}" >> "$ART/signals.json"
