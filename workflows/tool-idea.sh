#!/usr/bin/env bash
set -euo pipefail

# Tool Idea Generator — Uses LLM to propose useful tools based on
# current system needs, recent failures, and gaps.

ART="$PWD/artifacts"
mkdir -p "$ART"

SECRETS="/root/operator/conf/secrets.env"
if [ -f "$SECRETS" ]; then
  set -a; source "$SECRETS"; set +a
fi

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$PWD/log.txt"; }
log "Tool idea generation starting..."

# Gather context
EXISTING_TOOLS=$(ls /root/operator/tools/ 2>/dev/null || echo "none")
BACKLOG=$(cat /root/operator/knowledge/tools/backlog.md 2>/dev/null || echo "empty")
RECENT_FAILURES=$(find /root/operator/jobs -name job.json -newer /root/operator/jobs 2>/dev/null | sort | tail -10 | xargs grep -l '"FAILED"' 2>/dev/null | xargs cat 2>/dev/null | head -c 2000 || echo "none")
REGISTRY=$(cat /root/operator/knowledge/tools/registry.md 2>/dev/null || echo "empty")

python3 - "$EXISTING_TOOLS" "$BACKLOG" "$RECENT_FAILURES" "$REGISTRY" "$ART" <<'PY'
import json, sys, os

existing = sys.argv[1]
backlog = sys.argv[2]
failures = sys.argv[3]
registry = sys.argv[4]
art_dir = sys.argv[5]

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    with open(os.path.join(art_dir, "tool-idea.md"), "w") as f:
        f.write("# Tool Idea\n\nNo LLM available.\n")
    sys.exit(0)

from openai import OpenAI

client = OpenAI(api_key=api_key)

prompt = f"""You are the Tool Factory ideation module of an autonomous operator system.

Based on the current system state, propose ONE specific, high-impact tool that should be built.

EXISTING TOOLS:
{existing[:1500]}

TOOL BACKLOG:
{backlog[:1000]}

TOOL REGISTRY:
{registry[:1000]}

RECENT JOB FAILURES:
{failures[:1500]}

Requirements:
- The tool must solve a REAL problem visible in the data
- Must be implementable as a single bash or Python script
- Must produce measurable output
- Should NOT duplicate existing tools

Output valid JSON:
{{
  "name": "tool-name",
  "purpose": "What it does and why it matters",
  "type": "bash|python",
  "inputs": "What it takes as input",
  "outputs": "What it produces",
  "implementation_sketch": "10-20 line pseudocode or description",
  "impact": "How this improves the system",
  "priority": "high|medium|low"
}}"""

try:
    resp = client.responses.create(model="gpt-4.1-mini", input=prompt)
    import re
    text = resp.output_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    idea = json.loads(text)
except Exception as e:
    idea = {"name": "unknown", "purpose": f"LLM failed: {e}", "priority": "low"}

# Write structured output
with open(os.path.join(art_dir, "tool-idea.json"), "w") as f:
    json.dump(idea, f, indent=2)

# Write markdown
md = [
    f"# Tool Idea: {idea.get('name', 'unnamed')}",
    "",
    f"## Purpose",
    idea.get("purpose", "unknown"),
    "",
    f"## Type: {idea.get('type', 'unknown')}",
    f"## Priority: {idea.get('priority', 'unknown')}",
    "",
    f"## Inputs",
    idea.get("inputs", "unknown"),
    "",
    f"## Outputs",
    idea.get("outputs", "unknown"),
    "",
    f"## Implementation",
    idea.get("implementation_sketch", "unknown"),
    "",
    f"## Impact",
    idea.get("impact", "unknown"),
]

with open(os.path.join(art_dir, "tool-idea.md"), "w") as f:
    f.write("\n".join(md))

print(f"Tool idea: {idea.get('name')} ({idea.get('priority')})")
PY

log "Tool idea generation complete"
