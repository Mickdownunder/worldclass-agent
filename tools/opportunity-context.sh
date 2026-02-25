#!/usr/bin/env bash
set -e

OUT=/tmp/opportunity-context.txt

echo "=== RECENT JOBS ===" > $OUT
find /root/operator/jobs -name job.json | sort | tail -n 20 | xargs cat >> $OUT

echo -e "\n=== GOALS ===" >> $OUT
cat /root/operator/knowledge/goals/* 2>/dev/null || true >> $OUT

echo -e "\n=== PRIORITIES ===" >> $OUT
cat /root/operator/knowledge/priorities/* 2>/dev/null || true >> $OUT

echo -e "\n=== TOOL INVENTORY ===" >> $OUT
ls /root/operator/tools >> $OUT

echo $OUT
