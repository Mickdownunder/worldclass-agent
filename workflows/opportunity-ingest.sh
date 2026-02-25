#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

# latest llm output
LLM=$(find /root/operator/jobs -name llm.json -printf "%T@ %p\n" | sort -n | tail -n 1 | cut -d' ' -f2-)

if [ ! -f "$LLM" ]; then
  echo "no llm.json found" >> "$PWD/log.txt"
  exit 0
fi

OUT=/root/operator/knowledge/opportunities.md
mkdir -p /root/operator/knowledge

echo "# Opportunity Backlog" > "$ART/ingest.md"
echo "" >> "$ART/ingest.md"

python3 - <<PY
import json,os,datetime

llm="$LLM"
out="$OUT"

try:
    with open(llm) as f:
        raw = f.read().strip()
    if not raw:
        raise ValueError("llm.json is empty")
    data = json.loads(raw)
except (json.JSONDecodeError, ValueError) as e:
    # Fallback: try JSONL (one JSON object per line)
    data = []
    with open(llm) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    if not data:
        raise SystemExit(f"llm.json invalid or empty: {e}")

if not isinstance(data, list):
    data = [data] if isinstance(data, dict) else []

ts=datetime.datetime.utcnow().isoformat()

lines=[]
for o in data:
    if not isinstance(o, dict):
        continue
    line=f"- [{ts}] ({o.get('type','')}) {o.get('name','')} :: {o.get('reason','')}"
    lines.append(line)

with open(out,"a") as f:
    f.write("\n".join(lines)+"\n")

with open(os.environ["PWD"]+"/artifacts/ingest.md","w") as f:
    f.write("\n".join(lines))

print(len(lines),"opportunities ingested")
PY
