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
