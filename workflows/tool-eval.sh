#!/usr/bin/env bash
set -euo pipefail

# Tool Evaluator — Uses LLM to evaluate existing tools' effectiveness.

ART="$PWD/artifacts"
mkdir -p "$ART"

SECRETS="/root/operator/conf/secrets.env"
if [ -f "$SECRETS" ]; then
  set -a; source "$SECRETS"; set +a
fi

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$PWD/log.txt"; }
log "Tool evaluation starting..."

# Gather tool info
TOOLS_DIR="/root/operator/tools"
REGISTRY="/root/operator/knowledge/tools/registry.md"

python3 - "$TOOLS_DIR" "$REGISTRY" "$ART" <<'PY'
import json, sys, os, pathlib

tools_dir = pathlib.Path(sys.argv[1])
registry_path = sys.argv[2]
art_dir = sys.argv[3]

api_key = os.environ.get("OPENAI_API_KEY")

# Gather tool info
tools = []
for f in sorted(tools_dir.iterdir()):
    if f.is_file() and not f.name.startswith("."):
        try:
            content = f.read_text()[:500]
            tools.append({"name": f.name, "size": f.stat().st_size, "preview": content})
        except:
            pass

registry = ""
if os.path.exists(registry_path):
    registry = open(registry_path).read()[:2000]

if not api_key:
    with open(os.path.join(art_dir, "eval.md"), "w") as f:
        f.write(f"# Tool Evaluation\n\nTools found: {len(tools)}\nNo LLM available for evaluation.\n")
    sys.exit(0)

from openai import OpenAI

client = OpenAI(api_key=api_key)

tools_text = json.dumps(tools, indent=2)[:6000]

prompt = f"""You are evaluating the tool inventory of an autonomous operator system.

TOOLS ({len(tools)} total):
{tools_text}

REGISTRY:
{registry[:1500]}

For each tool, assess:
1. Is it useful and actively needed?
2. Is the implementation quality acceptable?
3. Should it be improved, deprecated, or replaced?

Output valid JSON:
{{
  "evaluations": [
    {{"name": "tool.py", "useful": true, "quality": 0.7, "recommendation": "improve|keep|deprecate", "notes": "..."}}
  ],
  "overall_health": 0.0-1.0,
  "top_improvement": "The most impactful tool improvement"
}}"""

try:
    resp = client.responses.create(model="gpt-4.1-mini", input=prompt)
    import re
    text = resp.output_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    result = json.loads(text)
except Exception as e:
    result = {"evaluations": [], "overall_health": 0.0, "error": str(e)}

with open(os.path.join(art_dir, "eval.json"), "w") as f:
    json.dump(result, f, indent=2)

md = ["# Tool Evaluation", ""]
for ev in result.get("evaluations", []):
    md.append(f"## {ev.get('name')}")
    md.append(f"- Quality: {ev.get('quality', '?')}")
    md.append(f"- Recommendation: {ev.get('recommendation', '?')}")
    md.append(f"- Notes: {ev.get('notes', '')}")
    md.append("")

md.append(f"## Overall Health: {result.get('overall_health', '?')}")
md.append(f"## Top Improvement: {result.get('top_improvement', 'none')}")

with open(os.path.join(art_dir, "eval.md"), "w") as f:
    f.write("\n".join(md))

print(f"Evaluated {len(result.get('evaluations',[]))} tools, health={result.get('overall_health')}")
PY

log "Tool evaluation complete"
