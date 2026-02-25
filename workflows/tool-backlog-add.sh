#!/usr/bin/env bash
set -e

BACKLOG="/root/operator/knowledge/tools/backlog.md"

if ! grep -q "infra-summary" "$BACKLOG"; then
  echo "- infra-summary" >> "$BACKLOG"
fi
