#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

# Erwartet signals.json im artifacts/ des Jobs (oder vom User kopiert)
SIG="$ART/signals.json"
if [ ! -f "$SIG" ]; then
  echo "signals.json missing in artifacts/" > "$ART/proposal.md"
  exit 0
fi

DISK=$(grep -oP '"disk_root_use":\s*"\K[^"]+' "$SIG" || echo "unknown")
LOAD=$(grep -oP '"load":\s*"\K[^"]+' "$SIG" || echo "unknown")

{
  echo "# Proposal: Infra"
  echo ""
  echo "## Signals"
  echo "- disk_root_use: $DISK"
  echo "- load: $LOAD"
  echo ""
  echo "## Suggested next job"
  echo "- Run infra-status daily"
  echo "- If disk_root_use > 80%: create cleanup proposal"
  echo ""
  echo "## Risk"
  echo "- READ_ONLY"
} > "$ART/proposal.md"
