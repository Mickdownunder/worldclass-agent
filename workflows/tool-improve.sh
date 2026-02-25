#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

TOOL_DIR="/root/operator/tools"

# create improved version
cat > "$TOOL_DIR/infra-summary-v2.sh" <<EOF
#!/usr/bin/env bash
echo "=== Infra Summary v2 ==="
echo ""
uptime
echo ""
df -h /
echo ""
free -h
echo ""
echo "Top processes:"
ps aux --sort=-%mem | head -5
EOF

chmod +x "$TOOL_DIR/infra-summary-v2.sh"

cat > "$ART/tool-improved.md" <<EOF
# Tool Improved

infra-summary → infra-summary-v2

Enhancement:
- added top process snapshot
EOF
