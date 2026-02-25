#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

OPP_MD="/root/operator/knowledge/opportunities.md"
if [ ! -f "$OPP_MD" ]; then
  echo "No opportunities backlog found at $OPP_MD" > "$ART/selected.md"
  cat > "$ART/selected.json" <<JSON
{"selected":[],"error":"no_backlog"}
JSON
  exit 0
fi

# configurable selection count
N="${SELECT_N:-3}"

# Select latest N lines (simple v1). Later: ranking.
SEL_LINES=$(tail -n 200 "$OPP_MD" | grep -E '^\- \[' | tail -n "$N" || true)

echo "# Selected Opportunities (v1)" > "$ART/selected.md"
echo "" >> "$ART/selected.md"
echo "$SEL_LINES" >> "$ART/selected.md"

python3 - <<PY
import os, json, re

n=int(os.environ.get("SELECT_N","3"))
opp_path="/root/operator/knowledge/opportunities.md"
out_json=os.path.join(os.environ["PWD"],"artifacts","selected.json")

lines=[]
with open(opp_path,"r",encoding="utf-8",errors="ignore") as f:
    for line in f.read().splitlines():
        if line.startswith("- ["):
            lines.append(line)

# take last n opportunities
sel=lines[-n:] if len(lines)>=n else lines

pat=re.compile(r'^\- \[(?P<ts>[^\]]+)\] \((?P<type>[^)]+)\) (?P<name>[^:]+) :: (?P<reason>.*)$')

selected=[]
for s in sel:
    m=pat.match(s.strip())
    if not m:
        continue
    selected.append(m.groupdict())

with open(out_json,"w",encoding="utf-8") as f:
    json.dump({"selected":selected}, f, indent=2)

print(f"selected={len(selected)}")
PY
