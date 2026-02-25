#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

BACKLOG="/root/operator/knowledge/tools/backlog.md"

if grep -q "infra-summary" "$BACKLOG"; then
  /root/operator/bin/op job new --workflow tool-improve --request "backlog improve infra-summary" \
    | xargs -I{} /root/operator/bin/op run {} >> "$PWD/log.txt" 2>&1
fi

cat > "$ART/backlog-improve.md" <<EOF
# Backlog Improve

Checked backlog and triggered improvements if candidates exist.
EOF

