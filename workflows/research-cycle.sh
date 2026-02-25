#!/usr/bin/env bash
# Run one phase of the research cycle for a project. Request = project_id.
# Phases: explore -> focus -> connect -> verify -> synthesize -> done
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
TOOLS="$OPERATOR_ROOT/tools"
RESEARCH="$OPERATOR_ROOT/research"
ART="$PWD/artifacts"
mkdir -p "$ART"

if [ -f "job.json" ]; then
  REQUEST=$(python3 -c "import json; d=json.load(open('job.json')); print(d.get('request',''), end='')")
fi
PROJECT_ID=$(echo "${REQUEST:-$*}" | awk '{print $1}')
if [ -z "$PROJECT_ID" ] || [ ! -d "$RESEARCH/$PROJECT_ID" ]; then
  echo "Usage: research-cycle.sh <project_id>"
  exit 2
fi

PROJ_DIR="$RESEARCH/$PROJECT_ID"
SECRETS="$OPERATOR_ROOT/conf/secrets.env"
[ -f "$SECRETS" ] && set -a && source "$SECRETS" && set +a

PHASE=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('phase','explore'), end='')")
QUESTION=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('question',''), end='')")

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$PWD/log.txt"; echo "$*" >&2; }

advance_phase() {
  local next_phase="$1"
  python3 - "$PROJ_DIR" "$next_phase" <<'PY'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
p = Path(sys.argv[1])
new_phase = sys.argv[2]
d = json.loads((p / "project.json").read_text())
d["phase"] = new_phase
d["last_phase_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
if new_phase == "done":
  d["status"] = "done"
(p / "project.json").write_text(json.dumps(d, indent=2))
PY
}

case "$PHASE" in
  explore)
    log "Phase: EXPLORE — search and read initial sources"
    python3 "$TOOLS/research_web_search.py" "$QUESTION" --max 12 > "$ART/web_search.json" 2>> "$PWD/log.txt" || true
    python3 "$TOOLS/research_academic.py" semantic_scholar "$QUESTION" --max 5 > "$ART/semantic_scholar.json" 2>> "$PWD/log.txt" || true
    python3 "$TOOLS/research_academic.py" arxiv "$QUESTION" --max 5 > "$ART/arxiv.json" 2>> "$PWD/log.txt" || true
    python3 - "$PROJ_DIR" "$ART" <<'PY'
import json, hashlib
from pathlib import Path
proj_dir, art = Path(sys.argv[1]), Path(sys.argv[2])
for name in ["web_search.json", "semantic_scholar.json", "arxiv.json"]:
  f = art / name
  if not f.exists(): continue
  try: data = json.loads(f.read_text())
  except: continue
  for item in (data if isinstance(data, list) else []):
    url = (item.get("url") or "").strip()
    if not url: continue
    fid = hashlib.sha256(url.encode()).hexdigest()[:12]
    (proj_dir / "sources" / f"{fid}.json").write_text(json.dumps({**item, "confidence": 0.5, "source_quality": "unknown"}))
PY
    # Read first 5 sources
    count=0
    for f in "$PROJ_DIR/sources"/*.json; do
      [ -f "$f" ] || continue
      [ $count -ge 5 ] && break
      url=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('url',''), end='')")
      [ -n "$url" ] || continue
      python3 "$TOOLS/research_web_reader.py" "$url" > "$ART/read_result.json" 2>> "$PWD/log.txt" || continue
      python3 - "$PROJ_DIR" "$ART" "$url" <<'INNER'
import json, hashlib
from pathlib import Path
proj_dir, art, url = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
data = json.loads((art / "read_result.json").read_text())
key = hashlib.sha256(url.encode()).hexdigest()[:12]
(proj_dir / "sources" / f"{key}_content.json").write_text(json.dumps(data))
text = (data.get("text") or data.get("abstract") or "")[:8000]
if text:
  fid = hashlib.sha256((url + text[:200]).encode()).hexdigest()[:12]
  (proj_dir / "findings" / f"{fid}.json").write_text(json.dumps({"url": url, "title": data.get("title",""), "excerpt": text[:2000], "source": "read", "confidence": 0.6}))
INNER
      count=$((count+1))
    done
    advance_phase "focus"
    ;;
  focus)
    log "Phase: FOCUS — gap analysis and targeted search"
    python3 "$TOOLS/research_reason.py" "$PROJECT_ID" gap_analysis > "$ART/gaps.json" 2>> "$PWD/log.txt" || true
    # One extra search from top gap and merge to project sources
    if [ -f "$ART/gaps.json" ]; then
      extra_query=$(python3 -c "
import json
d=json.load(open('$ART/gaps.json'))
gaps=d.get('gaps',[])[:1]
q=gaps[0].get('suggested_search','') if gaps else ''
print(q or '$QUESTION', end='')
")
      python3 "$TOOLS/research_web_search.py" "$extra_query" --max 5 > "$ART/focus_search.json" 2>> "$PWD/log.txt" || true
      python3 - "$PROJ_DIR" "$ART" <<'PY'
import json, hashlib
from pathlib import Path
proj_dir, art = Path(sys.argv[1]), Path(sys.argv[2])
f = art / "focus_search.json"
if f.exists():
  try:
    data = json.loads(f.read_text())
    for item in data:
      url = (item.get("url") or "").strip()
      if url:
        fid = hashlib.sha256(url.encode()).hexdigest()[:12]
        (proj_dir / "sources" / f"{fid}.json").write_text(json.dumps({**item, "confidence": 0.5}))
  except Exception: pass
PY
    fi
    advance_phase "connect"
    ;;
  connect)
    log "Phase: CONNECT — contradictions and hypotheses"
    python3 "$TOOLS/research_reason.py" "$PROJECT_ID" contradiction_detection > "$PROJ_DIR/contradictions.json" 2>> "$PWD/log.txt" || true
    python3 "$TOOLS/research_reason.py" "$PROJECT_ID" hypothesis_formation > "$ART/hypotheses.json" 2>> "$PWD/log.txt" || true
    if [ -f "$ART/hypotheses.json" ]; then
      python3 - "$PROJ_DIR" "$ART" <<'PY'
import json
from pathlib import Path
p = Path(sys.argv[1])
art = Path(sys.argv[2])
h = json.loads((art / "hypotheses.json").read_text())
hyps = h.get("hypotheses", [])[:1]
th = json.loads((p / "thesis.json").read_text())
th["current"] = hyps[0].get("statement", "") if hyps else ""
th["confidence"] = hyps[0].get("confidence", 0.5) if hyps else 0.0
th["evidence"] = [x.get("evidence_summary", "") for x in hyps]
(p / "thesis.json").write_text(json.dumps(th, indent=2))
PY
    fi
    advance_phase "verify"
    ;;
  verify)
    log "Phase: VERIFY — optional extra reads; then synthesize"
    advance_phase "synthesize"
    ;;
  synthesize)
    log "Phase: SYNTHESIZE — report"
    export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
    RESEARCH_SYNTHESIS_MODEL="${RESEARCH_SYNTHESIS_MODEL:-gpt-4.1-mini}"
    python3 - "$PROJ_DIR" "$ART" "$OPERATOR_ROOT" <<'PY'
import json, os, sys
from pathlib import Path
proj_dir, art, op_root = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
findings = []
for f in (proj_dir / "findings").glob("*.json"):
  try: findings.append(json.loads(f.read_text()))
  except: pass
project = json.loads((proj_dir / "project.json").read_text())
question = project.get("question", "")
contra = []
if (proj_dir / "contradictions.json").exists():
  try: contra = json.loads((proj_dir / "contradictions.json").read_text()).get("contradictions", [])
  except: pass
thesis = json.loads((proj_dir / "thesis.json").read_text())
items_text = json.dumps(findings[:30], indent=2, ensure_ascii=False)[:15000]
prompt = f"""You are a research analyst. Synthesize into a short structured report.

RESEARCH QUESTION: {question}

FINDINGS:
{items_text}

CURRENT THESIS: {thesis.get('current', '')} (confidence: {thesis.get('confidence', 0)})

CONTRADICTIONS TO NOTE: {json.dumps(contra)[:1000]}

Produce markdown: 1) Executive Summary. 2) Key Findings (bulleted, with source). 3) Contradictions/Gaps. 4) Conclusion/Thesis. 5) Suggested Next Steps."""
from openai import OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
model = os.environ.get("RESEARCH_SYNTHESIS_MODEL", "gpt-4.1-mini")
resp = client.responses.create(model=model, input=prompt)
report = (resp.output_text or "").strip()
(art / "report.md").write_text(report)
import datetime
ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
(proj_dir / "reports" / f"report_{ts}.md").write_text(report)
PY
    advance_phase "done"
    ;;
  done)
    log "Project already done."
    ;;
  *)
    log "Unknown phase: $PHASE; setting to explore"
    advance_phase "explore"
    ;;
esac

echo "Phase $PHASE complete." >> "$PWD/log.txt"
echo "done"
