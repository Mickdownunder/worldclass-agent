#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

cp /root/operator/knowledge/priorities.md "$ART/priorities.md"

cat > "$ART/priority-decision.md" <<EOF
# Priority Decision

High priority focus:
- Maintain system health
- Ensure autopilot continuity

Planner should favor infra and autopilot workflows.
EOF
