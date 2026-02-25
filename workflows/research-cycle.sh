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
# Phase history for loop-back limit (max 2 returns to same phase)
d.setdefault("phase_history", []).append(new_phase)
loop_count = d["phase_history"].count(new_phase)
if loop_count > 2:
  # Force advance to next phase instead of looping back
  order = ["explore", "focus", "connect", "verify", "synthesize", "done"]
  try:
    idx = order.index(new_phase)
    if idx < len(order) - 1:
      new_phase = order[idx + 1]
  except ValueError:
    pass
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
    # Rate-limit: throttle new findings per project per day (watchdog)
    OVER_LIMIT=0
    if [ -f "$TOOLS/research_watchdog.py" ]; then
      OVER_LIMIT=$(python3 "$TOOLS/research_watchdog.py" rate-limit "$PROJECT_ID" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(1 if d.get('over_limit') else 0, end='')" 2>/dev/null) || true
    fi
    python3 "$TOOLS/research_web_search.py" "$QUESTION" --max 12 > "$ART/web_search.json" 2>> "$PWD/log.txt" || true
    python3 "$TOOLS/research_academic.py" semantic_scholar "$QUESTION" --max 5 > "$ART/semantic_scholar.json" 2>> "$PWD/log.txt" || true
    python3 "$TOOLS/research_academic.py" arxiv "$QUESTION" --max 5 > "$ART/arxiv.json" 2>> "$PWD/log.txt" || true
    python3 - "$PROJ_DIR" "$ART" <<'PY'
import json, sys, hashlib
from pathlib import Path
proj_dir, art = Path(sys.argv[1]), Path(sys.argv[2])
for name in ["web_search.json", "semantic_scholar.json", "arxiv.json"]:
  f = art / name
  if not f.exists(): continue
  try: data = json.loads(f.read_text())
  except Exception: continue
  for item in (data if isinstance(data, list) else []):
    url = (item.get("url") or "").strip()
    if not url: continue
    fid = hashlib.sha256(url.encode()).hexdigest()[:12]
    (proj_dir / "sources" / f"{fid}.json").write_text(json.dumps({**item, "confidence": 0.5, "source_quality": "unknown"}))
PY
    # Read sources: dynamic limit from project config; cap to 0 if over rate-limit
    MAX_READ=$(python3 -c "
import json
from pathlib import Path
p = Path('$PROJ_DIR/project.json')
d = json.loads(p.read_text()) if p.exists() else {}
max_sources = d.get('config', {}).get('max_sources', 15)
base = min(max(10, max_sources), 50)
over = $OVER_LIMIT
print(0 if over else base, end='')
")
    if [ "$MAX_READ" -eq 0 ] && [ "$OVER_LIMIT" -eq 1 ]; then
      log "Rate limit reached — skipping new reads this cycle"
    fi
    count=0
    for f in "$PROJ_DIR/sources"/*.json; do
      [ -f "$f" ] || continue
      [ $count -ge "$MAX_READ" ] && break
      url=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('url',''), end='')")
      [ -n "$url" ] || continue
      python3 "$TOOLS/research_web_reader.py" "$url" > "$ART/read_result.json" 2>> "$PWD/log.txt" || continue
      python3 - "$PROJ_DIR" "$ART" "$url" <<'INNER'
import json, sys, hashlib
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
    # Top 3 gaps: run one search per gap and merge to project sources
    if [ -f "$ART/gaps.json" ]; then
      for gidx in 0 1 2; do
        [ ! -f "$ART/gaps.json" ] && break
        extra_query=$(python3 - "$ART/gaps.json" "$QUESTION" "$gidx" <<'GAPONE'
import json, sys
gaps_file, fallback, idx = sys.argv[1], sys.argv[2], int(sys.argv[3])
try:
  d = json.load(open(gaps_file))
  gaps = d.get("gaps", [])[:3]
  g = gaps[idx] if idx < len(gaps) else None
  q = (g.get("suggested_search", "") or fallback).strip()
  print(q, end="")
except Exception:
  print(fallback, end="")
GAPONE
)
        [ -z "$extra_query" ] && extra_query="$QUESTION"
        python3 "$TOOLS/research_web_search.py" "$extra_query" --max 5 > "$ART/focus_search_$gidx.json" 2>> "$PWD/log.txt" || true
      done
      python3 - "$PROJ_DIR" "$ART" <<'PY'
import json, sys, hashlib
from pathlib import Path
proj_dir, art = Path(sys.argv[1]), Path(sys.argv[2])
for name in ["focus_search.json", "focus_search_0.json", "focus_search_1.json", "focus_search_2.json"]:
  f = art / name
  if not f.exists():
    continue
  try:
    data = json.loads(f.read_text())
    for item in (data if isinstance(data, list) else []):
      url = (item.get("url") or "").strip()
      if url:
        fid = hashlib.sha256(url.encode()).hexdigest()[:12]
        (proj_dir / "sources" / f"{fid}.json").write_text(json.dumps({**item, "confidence": 0.5}))
  except Exception:
    pass
PY
    fi
    advance_phase "connect"
    ;;
  connect)
    log "Phase: CONNECT — contradictions, entity extraction, hypotheses"
    python3 "$TOOLS/research_entity_extract.py" "$PROJECT_ID" >> "$PWD/log.txt" 2>&1 || true
    python3 "$TOOLS/research_reason.py" "$PROJECT_ID" contradiction_detection > "$PROJ_DIR/contradictions.json" 2>> "$PWD/log.txt" || true
    python3 "$TOOLS/research_reason.py" "$PROJECT_ID" hypothesis_formation > "$ART/hypotheses.json" 2>> "$PWD/log.txt" || true
    if [ -f "$ART/hypotheses.json" ]; then
      python3 - "$PROJ_DIR" "$ART" <<'PY'
import json, sys
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
    log "Phase: VERIFY — source reliability, claim verification, fact-check"
    python3 "$TOOLS/research_verify.py" "$PROJECT_ID" source_reliability > "$ART/source_reliability.json" 2>> "$PWD/log.txt" || true
    python3 "$TOOLS/research_verify.py" "$PROJECT_ID" claim_verification > "$ART/claim_verification.json" 2>> "$PWD/log.txt" || true
    python3 "$TOOLS/research_verify.py" "$PROJECT_ID" fact_check > "$ART/fact_check.json" 2>> "$PWD/log.txt" || true
    # Persist verify artifacts to project for synthesize phase (may run in another job)
    mkdir -p "$PROJ_DIR/verify"
    [ -f "$ART/source_reliability.json" ] && cp "$ART/source_reliability.json" "$PROJ_DIR/verify/" 2>/dev/null || true
    [ -f "$ART/claim_verification.json" ] && cp "$ART/claim_verification.json" "$PROJ_DIR/verify/" 2>/dev/null || true
    [ -f "$ART/fact_check.json" ] && cp "$ART/fact_check.json" "$PROJ_DIR/verify/" 2>/dev/null || true
    # Mark low-reliability sources in project
    if [ -f "$ART/source_reliability.json" ]; then
      python3 - "$PROJ_DIR" "$ART" <<'VERIFY_PY'
import json, sys
from pathlib import Path
proj_dir, art = Path(sys.argv[1]), Path(sys.argv[2])
try:
  rel = json.loads((art / "source_reliability.json").read_text())
except Exception:
  sys.exit(0)
sources_dir = proj_dir / "sources"
for src in rel.get("sources", []):
  if src.get("reliability_score", 1.0) < 0.3:
    url = src.get("url", "")
    if not url:
      continue
    import hashlib
    fid = hashlib.sha256(url.encode()).hexdigest()[:12]
    f = sources_dir / f"{fid}.json"
    if f.exists():
      data = json.loads(f.read_text())
      data["low_reliability"] = True
      data["reliability_score"] = src.get("reliability_score", 0)
      f.write_text(json.dumps(data, indent=2))
VERIFY_PY
    fi
    # Loop-back to focus if too many unverified claims (max 2 returns)
    unverified=0
    if [ -f "$ART/claim_verification.json" ]; then
      unverified=$(python3 -c "
import json, sys
try:
  d = json.load(open(sys.argv[1]))
  claims = d.get('claims', [])
  n = sum(1 for c in claims if not c.get('verified', False))
  print(n, end='')
except Exception:
  print(0, end='')
" "$ART/claim_verification.json" 2>/dev/null) || unverified=0
    fi
    unverified=${unverified:-0}
    focus_count=$(python3 -c "
import json
try:
  d = json.load(open('$PROJ_DIR/project.json'))
  hist = d.get('phase_history', [])
  print(hist.count('focus'), end='')
except Exception:
  print(0, end='')
" 2>/dev/null) || focus_count=0
    focus_count=${focus_count:-0}
    if [ "${unverified:-0}" -gt 2 ] && [ "${focus_count:-0}" -lt 2 ]; then
      log "Too many unverified claims ($unverified) — looping back to focus"
      advance_phase "focus"
    else
      advance_phase "synthesize"
    fi
    ;;
  synthesize)
    log "Phase: SYNTHESIZE — report"
    export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
    export RESEARCH_SYNTHESIS_MODEL="${RESEARCH_SYNTHESIS_MODEL:-gpt-4.1-mini}"
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
# Verify artifacts: read from project verify/ (written by verify phase in same or previous run)
verify_dir = proj_dir / "verify"
rel_sources = {}
claims_verified = []
facts_note = ""
if (verify_dir / "source_reliability.json").exists():
  try:
    rel = json.loads((verify_dir / "source_reliability.json").read_text())
    rel_sources = {s.get("url"): s for s in rel.get("sources", [])}
  except: pass
if (verify_dir / "claim_verification.json").exists():
  try:
    cv = json.loads((verify_dir / "claim_verification.json").read_text())
    claims_verified = [c.get("claim", "") for c in cv.get("claims", []) if c.get("verified")]
  except: pass
if (verify_dir / "fact_check.json").exists():
  try:
    fc = json.loads((verify_dir / "fact_check.json").read_text())
    facts_note = json.dumps(fc.get("facts", [])[:15])[:800]
  except: pass
# Build findings text: mark low-reliability sources, add [VERIFIED] for verified claims
def finding_line(f):
  url = f.get("url", "")
  low = rel_sources.get(url, {}).get("reliability_score", 1) < 0.3
  tag = " [LOW RELIABILITY]" if low else ""
  return json.dumps({**f, "url": url + tag}, ensure_ascii=False)
items_text = json.dumps([json.loads(finding_line(f)) for f in findings[:30]], indent=2, ensure_ascii=False)[:15000]
verify_instruction = ""
if claims_verified or facts_note:
  verify_instruction = "\nVERIFIED CLAIMS (mark with [VERIFIED] in report where applicable): " + json.dumps(claims_verified[:20])[:500]
if facts_note:
  verify_instruction += "\nFACT-CHECK SUMMARY: " + facts_note
prompt = f"""You are a research analyst. Synthesize into a short structured report.

RESEARCH QUESTION: {question}

FINDINGS (sources marked [LOW RELIABILITY] should be cited with caution):
{items_text}

CURRENT THESIS: {thesis.get('current', '')} (confidence: {thesis.get('confidence', 0)})

CONTRADICTIONS TO NOTE: {json.dumps(contra)[:1000]}
{verify_instruction}

Produce markdown: 1) Executive Summary. 2) Key Findings (bulleted, with source; add [VERIFIED] for claims backed by 2+ sources). 3) Contradictions/Gaps. 4) Conclusion/Thesis. 5) Suggested Next Steps."""
from openai import OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
model = os.environ.get("RESEARCH_SYNTHESIS_MODEL", "gpt-4.1-mini")
resp = client.responses.create(model=model, input=prompt)
report = (resp.output_text or "").strip()
(art / "report.md").write_text(report)
from datetime import datetime, timezone
ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
(proj_dir / "reports" / f"report_{ts}.md").write_text(report)
PY
    # Quality Gate: critic pass, optionally revise if score < 0.6
    python3 "$TOOLS/research_critic.py" "$PROJECT_ID" critique "$ART" > "$ART/critique.json" 2>> "$PWD/log.txt" || true
    SCORE=0.5
    if [ -f "$ART/critique.json" ]; then
      SCORE=$(python3 -c "import json; d=json.load(open('$ART/critique.json')); print(d.get('score', 0.5), end='')" 2>/dev/null || echo "0.5")
    fi
    if [ -f "$ART/critique.json" ] && python3 -c "exit(0 if float('$SCORE') < 0.6 else 1)" 2>/dev/null; then
      log "Report quality low (score $SCORE). Revising..."
      python3 "$TOOLS/research_critic.py" "$PROJECT_ID" revise "$ART" > "$ART/revised_report.md" 2>> "$PWD/log.txt" || true
      if [ -f "$ART/revised_report.md" ] && [ -s "$ART/revised_report.md" ]; then
        cp "$ART/revised_report.md" "$ART/report.md"
        REV_TS=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'), end='')")
        cp "$ART/revised_report.md" "$PROJ_DIR/reports/report_${REV_TS}_revised.md"
      fi
    fi
    # Persist quality_gate and critique to project
    python3 - "$PROJ_DIR" "$ART" "$SCORE" <<'QG'
import json, sys
from pathlib import Path
proj_dir, art, score = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
d = json.loads((proj_dir / "project.json").read_text())
d.setdefault("quality_gate", {})["critic_score"] = score
d["quality_gate"]["revision_count"] = 1 if (art / "revised_report.md").exists() and (art / "revised_report.md").stat().st_size > 0 else 0
if (art / "critique.json").exists():
  try:
    c = json.loads((art / "critique.json").read_text())
    d["quality_gate"]["weaknesses_addressed"] = c.get("weaknesses", [])[:5]
  except Exception:
    pass
(proj_dir / "project.json").write_text(json.dumps(d, indent=2))
(proj_dir / "verify").mkdir(parents=True, exist_ok=True)
if (art / "critique.json").exists():
  (proj_dir / "verify" / "critique.json").write_text((art / "critique.json").read_text())
QG
    mkdir -p "$PROJ_DIR/verify"
    [ -f "$ART/critique.json" ] && cp "$ART/critique.json" "$PROJ_DIR/verify/" 2>/dev/null || true
    advance_phase "done"
    # Telegram: Forschung abgeschlossen
    if [ -x "$TOOLS/send-telegram.sh" ]; then
      MSG_FILE=$(mktemp)
      printf "Research abgeschlossen: %s\nFrage: %.200s\nReport: research/%s/reports/\n" "$PROJECT_ID" "$QUESTION" "$PROJECT_ID" >> "$MSG_FILE"
      "$TOOLS/send-telegram.sh" "$MSG_FILE" 2>/dev/null || true
      rm -f "$MSG_FILE"
    fi
    # Auto-Follow-up: neue Projekte aus Suggested Next Steps (opt-in)
    if [ "${RESEARCH_AUTO_FOLLOWUP:-0}" = "1" ] && [ -f "$TOOLS/research_auto_followup.py" ]; then
      python3 "$TOOLS/research_auto_followup.py" "$PROJECT_ID" >> "$PWD/log.txt" 2>&1 || true
    fi
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
