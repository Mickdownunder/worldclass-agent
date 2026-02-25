#!/usr/bin/env bash
set -euo pipefail

# Critic — LLM-powered evaluation of recent system performance.
# Reviews recent jobs, quality trends, and provides actionable feedback.

ART="$PWD/artifacts"
mkdir -p "$ART"

BRAIN="/root/operator/bin/brain"
SECRETS="/root/operator/conf/secrets.env"

if [ -f "$SECRETS" ]; then
  set -a; source "$SECRETS"; set +a
fi

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$PWD/log.txt"; }

log "Critic starting..."

# Gather recent context
RECENT_JOBS=$(find /root/operator/jobs -name job.json -newer /root/operator/jobs 2>/dev/null | sort | tail -20 | xargs -I{} cat {} 2>/dev/null || true)
MEMORY_STATE=$($BRAIN memory 2>/dev/null || echo '{}')
QUALITY=$($BRAIN quality 2>/dev/null || echo '{}')

# Use brain to reflect on overall system performance
python3 - "$RECENT_JOBS" "$MEMORY_STATE" "$QUALITY" "$ART" <<'PY'
import json, sys, os

recent_raw = sys.argv[1]
memory_raw = sys.argv[2]
quality_raw = sys.argv[3]
art_dir = sys.argv[4]

secrets_path = "/root/operator/conf/secrets.env"
api_key = None
if os.path.exists(secrets_path):
    for line in open(secrets_path):
        if line.startswith("OPENAI_API_KEY="):
            api_key = line.split("=", 1)[1].strip()

if not api_key:
    api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    with open(os.path.join(art_dir, "critique.md"), "w") as f:
        f.write("# Critique\n\nNo LLM available for evaluation.\n")
    sys.exit(0)

from openai import OpenAI
import re

client = OpenAI(api_key=api_key)

prompt = f"""You are the Critic module of an autonomous operator system.
Review the recent system performance and provide a thorough critique.

RECENT JOBS:
{recent_raw[:4000]}

MEMORY STATE:
{memory_raw[:2000]}

QUALITY METRICS:
{quality_raw[:1000]}

Provide your critique as markdown with these sections:
## Performance Summary
## What's Working Well
## Critical Issues
## Improvement Recommendations (specific, actionable)
## Quality Assessment (score 0-10, with justification)
## Priority Actions for Next Cycle

Be specific. Reference actual job IDs, workflows, and metrics.
Be constructive but honest. If things are broken, say so clearly."""

try:
    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )
    critique = resp.output_text.strip()
except Exception as e:
    critique = f"# Critique\n\nLLM evaluation failed: {e}\n"

with open(os.path.join(art_dir, "critique.md"), "w") as f:
    f.write(f"# System Critique — {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%d')}\n\n")
    f.write(critique)

print("Critique generated")
PY

log "Critic complete"
