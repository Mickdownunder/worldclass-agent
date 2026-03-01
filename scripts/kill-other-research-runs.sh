#!/usr/bin/env bash
# Kill all processes for research runs that are NOT proj-20260301-dd103ca8.
# Usage: ./kill-other-research-runs.sh
# Keeps: proj-20260301-dd103ca8
# Kills: proj-20260301-d96cea43, proj-20260301-5d6f40cc (and any other proj-* except dd103ca8)
set -euo pipefail

KEEP="proj-20260301-dd103ca8"

echo "Keeping: $KEEP"
echo "Stopping all other proj-* research runs..."

# Kill run-until-done.sh and deep_extract (and any tool) that contains another project id
for pid in $(pgrep -f "run-research-cycle-until-done.sh proj-" 2>/dev/null || true); do
  cmd=$(ps -p "$pid" -o args= 2>/dev/null || true)
  if [[ -n "$cmd" && "$cmd" != *"$KEEP"* ]]; then
    echo "  kill $pid ($cmd)"
    kill "$pid" 2>/dev/null || true
  fi
done

for pid in $(pgrep -f "research_deep_extract.py proj-" 2>/dev/null || true); do
  cmd=$(ps -p "$pid" -o args= 2>/dev/null || true)
  if [[ -n "$cmd" && "$cmd" != *"$KEEP"* ]]; then
    echo "  kill $pid (deep_extract)"
    kill "$pid" 2>/dev/null || true
  fi
done

# Kill op run jobs for other projects (op run /path/to/job where job.request = other project)
OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
for job_dir in "$OPERATOR_ROOT"/jobs/2026-03-01/*/; do
  [ -f "${job_dir}job.json" ] || continue
  req=$(python3 -c "import json; d=json.load(open('${job_dir}job.json')); print(d.get('request','')[:80])" 2>/dev/null || true)
  if [[ "$req" == *proj-* && "$req" != *"dd103ca8"* ]]; then
    job_id=$(basename "$job_dir")
    for pid in $(pgrep -f "op run.*$job_id" 2>/dev/null || true); do
      echo "  kill $pid (op run $job_id)"
      kill "$pid" 2>/dev/null || true
    done
  fi
done

echo "Done. Check: ps aux | grep research"
