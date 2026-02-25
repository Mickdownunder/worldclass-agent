#!/usr/bin/env bash
set -e

REG="/root/operator/knowledge/tools/registry.md"
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "- [$TS] infra-summary v1 created" >> "$REG"
echo "- [$TS] infra-summary v2 created" >> "$REG"
