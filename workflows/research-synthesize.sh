#!/usr/bin/env bash
# Synthesize findings into a report draft. Request = project_id.
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
RESEARCH="$OPERATOR_ROOT/research"
ART="$PWD/artifacts"
mkdir -p "$ART"

if [ -f "job.json" ]; then
  REQUEST=$(python3 -c "import json; d=json.load(open('job.json')); print(d.get('request',''), end='')")
fi
PROJECT_ID=$(echo "${REQUEST:-$*}" | awk '{print $1}')
if [ -z "$PROJECT_ID" ] || [ ! -d "$RESEARCH/$PROJECT_ID" ]; then
  echo "Usage: research-synthesize.sh <project_id>"
  exit 2
fi

PROJ_DIR="$RESEARCH/$PROJECT_ID"
SECRETS="$OPERATOR_ROOT/conf/secrets.env"
[ -f "$SECRETS" ] && set -a && source "$SECRETS" && set +a

# Gather all findings and run LLM synthesis
python3 - "$PROJ_DIR" "$ART" "$OPERATOR_ROOT" <<'PY'
import json, os, sys
from pathlib import Path
proj_dir, art, op_root = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
findings = []
for f in (proj_dir / "findings").glob("*.json"):
  try:
    findings.append(json.loads(f.read_text()))
  except Exception:
    pass
project = json.loads((proj_dir / "project.json").read_text())
question = project.get("question", "")

if not findings:
  (art / "report.md").write_text("# Report\n\nNo findings yet. Run research-search and research-read first.\n")
  sys.exit(0)

# Build context for LLM
items_text = json.dumps(findings[:30], indent=2, ensure_ascii=False)[:15000]
prompt = f"""You are a research analyst. Synthesize these findings into a short structured report.

RESEARCH QUESTION: {question}

FINDINGS (excerpts and sources):
{items_text}

Produce a markdown report with:
1. Executive Summary (2-3 sentences)
2. Key Findings (bulleted, with source URL where relevant)
3. Open Questions / Gaps
4. Suggested Next Steps

Be concise. Cite sources by URL or title."""

from openai import OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
resp = client.responses.create(model="gpt-4.1-mini", input=prompt)
report = (resp.output_text or "").strip()
(art / "report.md").write_text(report)
# Also save to project reports
from datetime import datetime, timezone
ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
(proj_dir / "reports" / f"report_{ts}.md").write_text(report)
PY

echo "Report written to $PROJ_DIR/reports/ and $ART/report.md" >> "$PWD/log.txt"
echo "done"
