#!/usr/bin/env bash
# Run one phase of the research cycle for a project. Request = project_id.
# Phases: explore -> focus -> connect -> verify -> synthesize -> done
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
TOOLS="$OPERATOR_ROOT/tools"
RESEARCH="$OPERATOR_ROOT/research"
ART="$PWD/artifacts"
# Use repo venv when present (research reader needs beautifulsoup4)
if [ -x "$OPERATOR_ROOT/.venv/bin/python3" ]; then
  export PATH="$OPERATOR_ROOT/.venv/bin:$PATH"
fi
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
    # Dependency preflight: must pass before any reader call (no silent 0 findings)
    # Capture stdout and stderr separately so we can include root cause on parse failure
    PREFLIGHT_ERR="$ART/preflight_stderr.txt"
    PREFLIGHT=$(python3 "$TOOLS/research_preflight.py" 2>"$PREFLIGHT_ERR" || true)
    echo "$PREFLIGHT" > "$ART/preflight_stdout.txt"
    PREFLIGHT_OK=$(echo "$PREFLIGHT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(1 if d.get('ok') else 0, end='')" 2>/dev/null) || echo "0"
    if [ "$PREFLIGHT_OK" != "1" ]; then
      log "Preflight failed — not running explore"
      python3 - "$PROJ_DIR" "$ART" <<'PREFLIGHT_FAIL'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
proj_dir, art = Path(sys.argv[1]), Path(sys.argv[2])
stdout_path = art / "preflight_stdout.txt"
stderr_path = art / "preflight_stderr.txt"
preflight_str = stdout_path.read_text().strip() if stdout_path.exists() else ""
stderr_content = stderr_path.read_text().strip()[:500] if stderr_path.exists() else ""
parse_msg = None
try:
  preflight = json.loads(preflight_str) if preflight_str else {}
except Exception as parse_err:
  preflight = {}
  stderr_suffix = f" stderr: {stderr_content}" if stderr_content else ""
  parse_msg = f"Preflight parse failed: {str(parse_err)[:200]}; raw (first 200 chars): {repr(preflight_str[:200])}{stderr_suffix}"
if not preflight or preflight.get("fail_code") is None:
  preflight = {"fail_code": "failed_dependency_preflight_error", "message": parse_msg or "Preflight parse failed"}
reasons = [preflight.get("message", "Dependency preflight failed")]
if stderr_content and stderr_content not in str(reasons):
  reasons.append("preflight_stderr: " + stderr_content[:300])
d = json.loads((proj_dir / "project.json").read_text())
d["status"] = preflight.get("fail_code") or "failed_dependency_preflight_error"
d.setdefault("quality_gate", {})["evidence_gate"] = {
  "status": "failed",
  "fail_code": preflight.get("fail_code"),
  "reasons": reasons,
  "metrics": {},
}
d["quality_gate"]["last_evidence_gate_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M:%SZ")
(proj_dir / "project.json").write_text(json.dumps(d, indent=2))
PREFLIGHT_FAIL
      echo "Preflight failed — project status set."
      exit 1
    fi
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
    read_attempts=0
    read_successes=0
    for f in "$PROJ_DIR/sources"/*.json; do
      [ -f "$f" ] || continue
      [ $read_attempts -ge "$MAX_READ" ] && break
      url=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('url',''), end='')")
      [ -n "$url" ] || continue
      read_attempts=$((read_attempts+1))
      python3 "$TOOLS/research_web_reader.py" "$url" > "$ART/read_result.json" 2>> "$PWD/log.txt" || true
      if [ -f "$ART/read_result.json" ]; then
        if python3 -c "
import json
try:
  d = json.load(open('$ART/read_result.json'))
  text = (d.get('text') or '').strip()
  err = (d.get('error') or '').strip()
  exit(0 if text and not err else 1)
except Exception:
  exit(1)
" 2>/dev/null; then
          read_successes=$((read_successes+1))
        fi
      fi
      python3 - "$PROJ_DIR" "$ART" "$url" <<'INNER'
import json, sys, hashlib
from pathlib import Path
proj_dir, art, url = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
if not (art / "read_result.json").exists():
  sys.exit(0)
data = json.loads((art / "read_result.json").read_text())
key = hashlib.sha256(url.encode()).hexdigest()[:12]
(proj_dir / "sources" / f"{key}_content.json").write_text(json.dumps(data))
text = (data.get("text") or data.get("abstract") or "")[:8000]
if text:
  fid = hashlib.sha256((url + text[:200]).encode()).hexdigest()[:12]
  (proj_dir / "findings" / f"{fid}.json").write_text(json.dumps({"url": url, "title": data.get("title",""), "excerpt": text[:2000], "source": "read", "confidence": 0.6}))
INNER
    done
    # Persist read stats for gate diagnosis; fail fast if 0 extractable content despite sources
    mkdir -p "$PROJ_DIR/explore"
    python3 - "$PROJ_DIR" "$read_attempts" "$read_successes" <<'STATS'
import json, sys
from pathlib import Path
proj_dir, attempts, successes = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
read_failures = max(0, attempts - successes)
(proj_dir / "explore" / "read_stats.json").write_text(json.dumps({
  "read_attempts": attempts,
  "read_successes": successes,
  "read_failures": read_failures,
}, indent=2))
STATS
    SOURCES_COUNT=$(python3 -c "
from pathlib import Path
p = Path('$PROJ_DIR/sources')
print(len([f for f in p.glob('*.json') if not f.name.endswith('_content.json')]), end='')
")
    if [ "$SOURCES_COUNT" -gt 0 ] && [ "$read_successes" -eq 0 ]; then
      log "Reader pipeline: 0 extractable content from $read_attempts read(s) — status failed_reader_no_extractable_content"
      python3 - "$PROJ_DIR" <<'READER_FAIL'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
proj_dir = Path(sys.argv[1])
d = json.loads((proj_dir / "project.json").read_text())
d["status"] = "failed_reader_no_extractable_content"
d.setdefault("quality_gate", {})["evidence_gate"] = {
  "status": "failed",
  "fail_code": "failed_reader_no_extractable_content",
  "reasons": ["zero_extractable_sources", "read_successes=0 with sources present"],
  "metrics": {"read_attempts": 0, "read_successes": 0, "read_failures": 0},
}
stats_file = proj_dir / "explore" / "read_stats.json"
if stats_file.exists():
  try:
    stats = json.loads(stats_file.read_text())
    d["quality_gate"]["evidence_gate"]["metrics"].update(stats)
  except Exception:
    pass
d["quality_gate"]["last_evidence_gate_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
(proj_dir / "project.json").write_text(json.dumps(d, indent=2))
READER_FAIL
      echo "Reader pipeline: 0 extractable content — project status set."
      exit 1
    fi
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
    # Claim ledger: deterministic is_verified (V3)
    python3 "$TOOLS/research_verify.py" "$PROJECT_ID" claim_ledger > "$ART/claim_ledger.json" 2>> "$PWD/log.txt" || true
    [ -f "$ART/claim_ledger.json" ] && cp "$ART/claim_ledger.json" "$PROJ_DIR/verify/" 2>/dev/null || true
    # Evidence Gate: must pass before synthesize
    GATE_RESULT=$(python3 "$TOOLS/research_quality_gate.py" "$PROJECT_ID" 2>> "$PWD/log.txt" || echo '{"pass":false}')
    GATE_PASS=$(echo "$GATE_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(1 if d.get('pass') else 0, end='')" 2>/dev/null) || echo "0"
    if [ "$GATE_PASS" != "1" ]; then
      log "Evidence gate failed — not advancing to synthesize"
      python3 - "$PROJ_DIR" "$GATE_RESULT" <<'GATE_FAIL'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
proj_dir, gate_str = Path(sys.argv[1]), sys.argv[2]
try:
  gate = json.loads(gate_str)
except Exception:
  gate = {"fail_code": "failed_insufficient_evidence", "metrics": {}, "reasons": []}
d = json.loads((proj_dir / "project.json").read_text())
d["status"] = gate.get("fail_code") or "failed_insufficient_evidence"
d.setdefault("quality_gate", {})["evidence_gate"] = {"status": "failed", "fail_code": gate.get("fail_code"), "metrics": gate.get("metrics", {}), "reasons": gate.get("reasons", [])}
d["quality_gate"]["last_evidence_gate_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
(proj_dir / "project.json").write_text(json.dumps(d, indent=2))
GATE_FAIL
    else
    echo "$GATE_RESULT" > "$ART/evidence_gate_result.json" 2>/dev/null || true
    python3 - "$PROJ_DIR" "$ART" <<'GATE_PASS'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
proj_dir, art = Path(sys.argv[1]), Path(sys.argv[2])
gate = {}
if (art / "evidence_gate_result.json").exists():
  try:
    gate = json.loads((art / "evidence_gate_result.json").read_text())
  except Exception:
    pass
d = json.loads((proj_dir / "project.json").read_text())
d.setdefault("quality_gate", {})["evidence_gate"] = {"status": "passed", "metrics": gate.get("metrics", {}), "reasons": []}
d["quality_gate"]["last_evidence_gate_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
(proj_dir / "project.json").write_text(json.dumps(d, indent=2))
GATE_PASS
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
    # Evidence gate passed — advance to synthesize (no loop-back; gate already enforces evidence)
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
# Verify artifacts: read from project verify/ (written by verify phase)
verify_dir = proj_dir / "verify"
rel_sources = {}
facts_note = ""
if (verify_dir / "source_reliability.json").exists():
  try:
    rel = json.loads((verify_dir / "source_reliability.json").read_text())
    rel_sources = {s.get("url"): s for s in rel.get("sources", [])}
  except: pass
if (verify_dir / "fact_check.json").exists():
  try:
    fc = json.loads((verify_dir / "fact_check.json").read_text())
    facts_note = json.dumps(fc.get("facts", [])[:15])[:800]
  except: pass
# Synthesis gets neutral data; [VERIFIED] is added deterministically later from claim_ledger
def finding_line(f):
  url = f.get("url", "")
  low = rel_sources.get(url, {}).get("reliability_score", 1) < 0.3
  tag = " [LOW RELIABILITY]" if low else ""
  return json.dumps({**f, "url": url + tag}, ensure_ascii=False)
items_text = json.dumps([json.loads(finding_line(f)) for f in findings[:30]], indent=2, ensure_ascii=False)[:15000]
verify_instruction = "\nDo NOT add [VERIFIED] tags yourself; they will be added automatically from the claim ledger."
if facts_note:
  verify_instruction += "\nFACT-CHECK SUMMARY: " + facts_note
prompt = f"""You are a research analyst. Synthesize into a short structured report.

RESEARCH QUESTION: {question}

FINDINGS (sources marked [LOW RELIABILITY] should be cited with caution):
{items_text}

CURRENT THESIS: {thesis.get('current', '')} (confidence: {thesis.get('confidence', 0)})

CONTRADICTIONS TO NOTE: {json.dumps(contra)[:1000]}
{verify_instruction}

Produce markdown: 1) Executive Summary. 2) Key Findings (bulleted, with source). 3) Contradictions/Gaps. 4) Conclusion/Thesis. 5) Suggested Next Steps."""
from openai import OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
model = os.environ.get("RESEARCH_SYNTHESIS_MODEL", "gpt-4.1-mini")
resp = client.responses.create(model=model, input=prompt)
report = (resp.output_text or "").strip()
from datetime import datetime, timezone
ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
# Deterministic [VERIFIED] from claim_ledger (V3): strip all existing [VERIFIED] first, then only ledger-is_verified get the tag
claim_ledger = []
if (verify_dir / "claim_ledger.json").exists():
  try:
    claim_ledger = json.loads((verify_dir / "claim_ledger.json").read_text()).get("claims", [])
  except: pass
import sys
sys.path.insert(0, str(op_root))
from tools.research_verify import apply_verified_tags_to_report
report = apply_verified_tags_to_report(report, claim_ledger)
(art / "report.md").write_text(report)
(proj_dir / "reports" / f"report_{ts}.md").write_text(report)
# Audit: claim_evidence_map per report (include verification_reason for UI: verified/disputed/unverified)
claim_evidence_map = {"report_id": f"report_{ts}.md", "ts": ts, "claims": []}
for c in claim_ledger:
  claim_evidence_map["claims"].append({
    "claim_id": c.get("claim_id"),
    "text": (c.get("text") or "")[:500],
    "is_verified": c.get("is_verified"),
    "verification_reason": c.get("verification_reason"),
    "supporting_source_ids": c.get("supporting_source_ids", []),
  })
(proj_dir / "reports" / f"claim_evidence_map_{ts}.json").write_text(json.dumps(claim_evidence_map, indent=2))
(proj_dir / "verify" / "claim_evidence_map_latest.json").write_text(json.dumps(claim_evidence_map, indent=2))
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
      # Re-check score after revision; if still low, fail with failed_quality_gate (V3)
      SCORE=$(python3 -c "import json; d=json.load(open('$ART/critique.json')); print(d.get('score', 0.5), end='')" 2>/dev/null || echo "0.5")
    fi
    if python3 -c "exit(0 if float('$SCORE') < 0.6 else 1)" 2>/dev/null; then
      log "Quality gate failed (score $SCORE) — status failed_quality_gate"
      python3 - "$PROJ_DIR" "$ART" "$SCORE" <<'QF_FAIL'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
proj_dir, art, score = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
d = json.loads((proj_dir / "project.json").read_text())
d["status"] = "failed_quality_gate"
d.setdefault("quality_gate", {})["critic_score"] = score
d["quality_gate"]["quality_gate_status"] = "failed"
d["quality_gate"]["fail_code"] = "failed_quality_gate"
(proj_dir / "project.json").write_text(json.dumps(d, indent=2))
QF_FAIL
    else
    # Persist quality_gate and critique to project (passed)
    python3 - "$PROJ_DIR" "$ART" "$SCORE" <<'QG'
import json, sys
from pathlib import Path
proj_dir, art, score = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
d = json.loads((proj_dir / "project.json").read_text())
d.setdefault("quality_gate", {})["critic_score"] = score
d["quality_gate"]["quality_gate_status"] = "passed"
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
    # Telegram: Forschung abgeschlossen (only when passed)
    if [ -x "$TOOLS/send-telegram.sh" ]; then
      MSG_FILE=$(mktemp)
      printf "Research abgeschlossen: %s\nFrage: %.200s\nReport: research/%s/reports/\n" "$PROJECT_ID" "$QUESTION" "$PROJECT_ID" >> "$MSG_FILE"
      "$TOOLS/send-telegram.sh" "$MSG_FILE" 2>/dev/null || true
      rm -f "$MSG_FILE"
    fi
    if [ "${RESEARCH_AUTO_FOLLOWUP:-0}" = "1" ] && [ -f "$TOOLS/research_auto_followup.py" ]; then
      python3 "$TOOLS/research_auto_followup.py" "$PROJECT_ID" >> "$PWD/log.txt" 2>&1 || true
    fi
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
