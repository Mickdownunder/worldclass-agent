#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

KNOW="/root/operator/knowledge/global"
mkdir -p "$KNOW"

TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "- [$TS] Autopilot ran successfully" >> "$KNOW/operator-log.md"

cat > "$ART/knowledge_commit.md" <<EOF
# Knowledge Commit

Entry added to operator-log.md

Timestamp: $TS
Policy: $JOB_POLICY
EOF
