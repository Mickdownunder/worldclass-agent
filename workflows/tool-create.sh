#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

TOOL_DIR="/root/operator/tools"
mkdir -p "$TOOL_DIR"

cat > "$TOOL_DIR/infra-summary.sh" <<EOF
#!/usr/bin/env bash
echo "=== Infra Summary ==="
echo ""
uptime
echo ""
df -h /
echo ""
free -h
EOF

chmod +x "$TOOL_DIR/infra-summary.sh"

cat > "$ART/tool-created.md" <<EOF
# Tool Created

Name: infra-summary
Location: /root/operator/tools/infra-summary.sh
EOF
