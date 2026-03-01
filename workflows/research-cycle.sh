#!/usr/bin/env bash
# Run one phase of the research cycle for a project. Request = project_id.
# Phases: explore -> focus -> connect -> verify -> synthesize -> done
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
export OPERATOR_ROOT
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
export RESEARCH_PROJECT_ID="$PROJECT_ID"
# All tool stderr and pipeline messages go to project log for easier debugging
CYCLE_LOG="$PROJ_DIR/log.txt"
SECRETS="$OPERATOR_ROOT/conf/secrets.env"
[ -f "$SECRETS" ] && set -a && source "$SECRETS" && set +a
POLICY="$OPERATOR_ROOT/conf/policy.env"
[ -f "$POLICY" ] && set -a && source "$POLICY" && set +a
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"
export RESEARCH_SYNTHESIS_MODEL="${RESEARCH_SYNTHESIS_MODEL:-gemini-3.1-pro-preview}"
export RESEARCH_CRITIQUE_MODEL="${RESEARCH_CRITIQUE_MODEL:-gpt-5.2}"
export RESEARCH_VERIFY_MODEL="${RESEARCH_VERIFY_MODEL:-gemini-3.1-pro-preview}"
export RESEARCH_HYPOTHESIS_MODEL="${RESEARCH_HYPOTHESIS_MODEL:-gemini-3.1-pro-preview}"

# Core 10 tool integration: Welle 1 on by default (knowledge_seed, question_graph, context_manager, academic)
export RESEARCH_ENABLE_KNOWLEDGE_SEED="${RESEARCH_ENABLE_KNOWLEDGE_SEED:-1}"
export RESEARCH_ENABLE_QUESTION_GRAPH="${RESEARCH_ENABLE_QUESTION_GRAPH:-1}"
export RESEARCH_ENABLE_ACADEMIC="${RESEARCH_ENABLE_ACADEMIC:-1}"
export RESEARCH_ENABLE_TOKEN_GOVERNOR="${RESEARCH_ENABLE_TOKEN_GOVERNOR:-0}"
export RESEARCH_ENABLE_RELEVANCE_GATE="${RESEARCH_ENABLE_RELEVANCE_GATE:-0}"
export RESEARCH_ENABLE_CONTEXT_MANAGER="${RESEARCH_ENABLE_CONTEXT_MANAGER:-1}"
export RESEARCH_ENABLE_DYNAMIC_OUTLINE="${RESEARCH_ENABLE_DYNAMIC_OUTLINE:-0}"
export RESEARCH_ENABLE_CLAIM_STATE_MACHINE="${RESEARCH_ENABLE_CLAIM_STATE_MACHINE:-0}"
export RESEARCH_ENABLE_CONTRADICTION_LINKING="${RESEARCH_ENABLE_CONTRADICTION_LINKING:-0}"
export RESEARCH_ENABLE_FALSIFICATION_GATE="${RESEARCH_ENABLE_FALSIFICATION_GATE:-0}"

# Don't send LLM API traffic through HTTP_PROXY (prevents 403 from proxy)
export NO_PROXY="${NO_PROXY:+$NO_PROXY,}api.openai.com,openai.com,generativelanguage.googleapis.com"
export no_proxy="${no_proxy:+$no_proxy,}api.openai.com,openai.com,generativelanguage.googleapis.com"

PHASE=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('phase','explore'), end='')")
QUESTION=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('question',''), end='')")
MEMORY_STRATEGY_FILE="$PROJ_DIR/memory_strategy.json"
RESEARCH_MEMORY_RELEVANCE_THRESHOLD="${RESEARCH_MEMORY_RELEVANCE_THRESHOLD:-0.50}"
RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON="${RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON:-{}}"
RESEARCH_MEMORY_CRITIC_THRESHOLD="${RESEARCH_MEMORY_CRITIC_THRESHOLD:-}"
RESEARCH_MEMORY_REVISE_ROUNDS="${RESEARCH_MEMORY_REVISE_ROUNDS:-2}"
if [ "${RESEARCH_MEMORY_V2_ENABLED:-1}" = "1" ] && [ -f "$MEMORY_STRATEGY_FILE" ]; then
  RESEARCH_MEMORY_RELEVANCE_THRESHOLD=$(python3 -c "
import json
from pathlib import Path
p = Path('$MEMORY_STRATEGY_FILE')
v = 0.50
if p.exists():
  try:
    d = json.loads(p.read_text())
    policy = ((d.get('selected_strategy') or {}).get('policy') or {})
    v = float(policy.get('relevance_threshold', 0.50))
  except Exception:
    pass
print(max(0.50, min(0.65, v)), end='')") || RESEARCH_MEMORY_RELEVANCE_THRESHOLD="0.50"
  RESEARCH_MEMORY_CRITIC_THRESHOLD=$(python3 -c "
import json
from pathlib import Path
p = Path('$MEMORY_STRATEGY_FILE')
v = ''
if p.exists():
  try:
    d = json.loads(p.read_text())
    policy = ((d.get('selected_strategy') or {}).get('policy') or {})
    if policy.get('critic_threshold') is not None:
      v = str(max(0.50, min(0.55, float(policy.get('critic_threshold')))))
  except Exception:
    pass
print(v, end='')") || RESEARCH_MEMORY_CRITIC_THRESHOLD=""
  RESEARCH_MEMORY_REVISE_ROUNDS=$(python3 -c "
import json
from pathlib import Path
p = Path('$MEMORY_STRATEGY_FILE')
v = 2
if p.exists():
  try:
    d = json.loads(p.read_text())
    policy = ((d.get('selected_strategy') or {}).get('policy') or {})
    v = int(policy.get('revise_rounds', 2))
  except Exception:
    pass
print(max(1, min(4, v)), end='')") || RESEARCH_MEMORY_REVISE_ROUNDS="2"
  RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON=$(python3 -c "
import json
from pathlib import Path
p = Path('$MEMORY_STRATEGY_FILE')
out = {}
if p.exists():
  try:
    d = json.loads(p.read_text())
    policy = ((d.get('selected_strategy') or {}).get('policy') or {})
    o = policy.get('domain_rank_overrides') or {}
    if isinstance(o, dict):
      out = o
  except Exception:
    pass
print(json.dumps(out), end='')") || RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON="{}"
fi
export RESEARCH_MEMORY_RELEVANCE_THRESHOLD
export RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON
export RESEARCH_MEMORY_CRITIC_THRESHOLD
export RESEARCH_MEMORY_REVISE_ROUNDS

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$CYCLE_LOG" 2>/dev/null; echo "$*" >&2; }
log "Cycle started: project=$PROJECT_ID phase=$PHASE"

# ── Terminal status guard: if project is dead, don't run ──
_STATUS=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('status',''), end='')" 2>/dev/null || echo "")
case "$_STATUS" in
  failed*|cancelled|abandoned)
    log "Project $PROJECT_ID has terminal status '$_STATUS' — skipping cycle"
    exit 0
    ;;
esac

# ── Project-level lock: only one research-cycle per project at a time ──
CYCLE_LOCK="$PROJ_DIR/.cycle.lock"
exec 9>"$CYCLE_LOCK"
if ! flock -n 9; then
  log "Another research-cycle is already running for $PROJECT_ID — skipping."
  exit 0
fi

progress_start() { python3 "$TOOLS/research_progress.py" start "$PROJECT_ID" "$1" 2>/dev/null || true; }
progress_step() { python3 "$TOOLS/research_progress.py" step "$PROJECT_ID" "$1" "${2:-}" "${3:-}" 2>/dev/null || true; }
progress_done() { python3 "$TOOLS/research_progress.py" done "$PROJECT_ID" 2>/dev/null || true; }

log_v2_mode_for_cycle() {
  python3 - "$PROJ_DIR" "$OPERATOR_ROOT" "$PROJECT_ID" "$PHASE" <<'MEMORY_V2_MODE' 2>> "$CYCLE_LOG" || true
import json, os, sys
from pathlib import Path
proj_dir, op_root, project_id, phase = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
sys.path.insert(0, str(op_root))
mode = "v2_disabled"
reason = "flag_off"
confidence = 1.0
details = {"mode": mode, "fallback_reason": reason}
if os.environ.get("RESEARCH_MEMORY_V2_ENABLED", "1").strip() == "1":
    ms = proj_dir / "memory_strategy.json"
    if not ms.exists():
        mode = "v2_fallback"
        reason = "no_strategy"
        confidence = 0.3
        details = {"mode": mode, "fallback_reason": reason}
    else:
        try:
            data = json.loads(ms.read_text())
            mode = str(data.get("mode") or "v2_applied")
            reason = data.get("fallback_reason")
            confidence = float(((data.get("selected_strategy") or {}).get("confidence")) or data.get("confidence") or 0.5)
            details = {
                "mode": mode,
                "fallback_reason": reason,
                "strategy_profile_id": ((data.get("selected_strategy") or {}).get("id")),
                "strategy_name": ((data.get("selected_strategy") or {}).get("name")),
                "confidence": confidence,
                "confidence_drivers": data.get("confidence_drivers") or {},
                "similar_episode_count": data.get("similar_episode_count", 0),
            }
        except Exception:
            mode = "v2_fallback"
            reason = "exception"
            confidence = 0.2
            details = {"mode": mode, "fallback_reason": reason}
try:
    from lib.memory import Memory
    with Memory() as mem:
        mem.record_memory_decision(
            decision_type="v2_mode",
            details=details,
            project_id=project_id,
            phase=phase,
            strategy_profile_id=details.get("strategy_profile_id"),
            confidence=max(0.0, min(1.0, confidence)),
        )
except Exception:
    pass
MEMORY_V2_MODE
}

# Pause-on-Rate-Limit: if project was paused, check if enough time passed (30 min cooldown)
if [ "$PHASE" != "done" ]; then
  PROJ_STATUS=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('status',''), end='')")
  if [ "$PROJ_STATUS" = "paused_rate_limited" ]; then
    COOLDOWN_OK=$(python3 -c "
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
d = json.loads(Path('$PROJ_DIR/project.json').read_text())
last = d.get('last_phase_at', '')
if last:
    t = datetime.fromisoformat(last.replace('Z', '+00:00'))
    if datetime.now(timezone.utc) - t < timedelta(minutes=30):
        print('0', end='')
    else:
        print('1', end='')
else:
    print('1', end='')" 2>/dev/null) || COOLDOWN_OK="1"
    if [ "$COOLDOWN_OK" != "1" ]; then
      log "Project still in cooldown after rate limit — skipping"
      exit 0
    fi
    # Reset status to allow retry
    python3 -c "
import json; from pathlib import Path
p = Path('$PROJ_DIR/project.json')
d = json.loads(p.read_text())
d['status'] = 'in_progress'
p.write_text(json.dumps(d, indent=2))"
  fi
fi

# Budget Circuit Breaker: abort if spend exceeds limit
if [ "$PHASE" != "done" ] && [ -f "$TOOLS/research_budget.py" ]; then
  BUDGET_OK=$(python3 "$TOOLS/research_budget.py" check "$PROJECT_ID" 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(1 if d.get('ok') else 0, end='')" 2>/dev/null) || BUDGET_OK="1"
  if [ "$BUDGET_OK" != "1" ]; then
    log "Budget exceeded — setting status FAILED_BUDGET_EXCEEDED"
    python3 -c "
import json
from pathlib import Path
from datetime import datetime, timezone
p = Path('$PROJ_DIR/project.json')
d = json.loads(p.read_text())
d['status'] = 'FAILED_BUDGET_EXCEEDED'
d['completed_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
p.write_text(json.dumps(d, indent=2))"
    exit 0
  fi
fi

# Memory v2 mode observability: exactly one mode decision per cycle run.
log_v2_mode_for_cycle

advance_phase() {
  local next_phase="$1"
  log "advance_phase: requesting $next_phase"
  # Conductor hybrid gate: ask conductor if we should really advance (unless gate disabled or conductor is master)
  if [ -f "$TOOLS/research_conductor.py" ] && [ "${RESEARCH_CONDUCTOR_GATE:-1}" != "0" ] && [ "${RESEARCH_USE_CONDUCTOR:-0}" != "1" ]; then
    local conductor_next
    conductor_next=$(python3 "$TOOLS/research_conductor.py" gate "$PROJECT_ID" "$next_phase" 2>>/dev/null) || true
    if [ -n "$conductor_next" ] && [ "$conductor_next" != "$next_phase" ]; then
      log "Conductor override: $next_phase -> $conductor_next (re-running phase)"
      next_phase="$conductor_next"
      progress_step "Conductor: weitere ${next_phase}-Runde"
    fi
  fi
  python3 "$TOOLS/research_advance_phase.py" "$PROJ_DIR" "$next_phase"
  log "advance_phase: set phase=$next_phase"
}

persist_v2_episode() {
  local run_status="$1"
  python3 - "$PROJ_DIR" "$OPERATOR_ROOT" "$PROJECT_ID" "$run_status" <<'MEMORY_V2_EPISODE' 2>> "$CYCLE_LOG" || true
import json, sys
from collections import Counter
from pathlib import Path
proj_dir, op_root, project_id, run_status = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
sys.path.insert(0, str(op_root))
try:
    project = json.loads((proj_dir / "project.json").read_text())
except Exception:
    project = {}
plan_queries = []
plan_path = proj_dir / "research_plan.json"
if plan_path.exists():
    try:
        plan_queries = json.loads(plan_path.read_text()).get("queries", [])
    except Exception:
        plan_queries = []
mix_counter = Counter()
for q in plan_queries:
    qtype = str((q or {}).get("type") or "web").lower()
    if qtype not in {"web", "academic", "medical"}:
        qtype = "web"
    mix_counter[qtype] += 1
plan_mix = {}
if mix_counter:
    total = sum(mix_counter.values())
    plan_mix = {k: round(v / total, 3) for k, v in mix_counter.items()}
source_counter = Counter()
for sf in (proj_dir / "sources").glob("*.json"):
    if sf.name.endswith("_content.json"):
        continue
    try:
        sd = json.loads(sf.read_text())
    except Exception:
        continue
    url = (sd.get("url") or "").strip()
    if "://" in url:
        domain = url.split("/")[2].replace("www.", "")
        if domain:
            source_counter[domain] += 1
source_mix = dict(source_counter.most_common(10))
qg = project.get("quality_gate", {}) if isinstance(project.get("quality_gate"), dict) else {}
evidence_gate = qg.get("evidence_gate", {}) if isinstance(qg.get("evidence_gate"), dict) else {}
gate_metrics = evidence_gate.get("metrics", {}) if isinstance(evidence_gate.get("metrics"), dict) else {}
critic_score = qg.get("critic_score")
if not isinstance(critic_score, (int, float)):
    critic_score = None
strategy_profile_id = None
strategy_name = None
memory_mode = "fallback"
strategy_confidence = None
ms = proj_dir / "memory_strategy.json"
if ms.exists():
    try:
        ms_data = json.loads(ms.read_text())
        selected = (ms_data.get("selected_strategy") or {})
        strategy_profile_id = selected.get("id")
        strategy_name = selected.get("name")
        raw_mode = (ms_data.get("mode") or "").strip().lower()
        memory_mode = "applied" if raw_mode == "v2_applied" else "fallback"
        strategy_confidence = ms_data.get("confidence") or selected.get("confidence")
        if strategy_confidence is not None:
            strategy_confidence = float(strategy_confidence)
    except Exception:
        pass
fail_codes = []
status = str(project.get("status") or run_status or "unknown")
if status.startswith("failed") or status in {"aem_blocked", "cancelled"}:
    fail_codes.append(status)
what_helped = []
if gate_metrics.get("verified_claim_count", 0) >= 3:
    what_helped.append("multi_source_verification")
if gate_metrics.get("claim_support_rate", 0) >= 0.6:
    what_helped.append("high_claim_support_rate")
what_hurt = []
if status.startswith("failed"):
    what_hurt.append(status)
if gate_metrics.get("claim_support_rate", 1) < 0.4:
    what_hurt.append("low_claim_support_rate")
from lib.memory import Memory
verified_claim_count = gate_metrics.get("verified_claim_count")
claim_support_rate = gate_metrics.get("claim_support_rate")
if verified_claim_count is not None:
    verified_claim_count = int(verified_claim_count)
if claim_support_rate is not None:
    claim_support_rate = float(claim_support_rate)
with Memory() as mem:
    episode_id = mem.record_run_episode(
        project_id=project_id,
        question=str(project.get("question") or ""),
        domain=str(project.get("domain") or "general"),
        status=status,
        plan_query_mix=plan_mix,
        source_mix=source_mix,
        gate_metrics=gate_metrics,
        critic_score=critic_score,
        user_verdict="approved" if status == "done" else "rejected" if status.startswith("failed") else "none",
        fail_codes=fail_codes,
        what_helped=what_helped,
        what_hurt=what_hurt,
        strategy_profile_id=strategy_profile_id,
        memory_mode=memory_mode,
        strategy_confidence=strategy_confidence,
        verified_claim_count=verified_claim_count,
        claim_support_rate=claim_support_rate,
    )
    mem.record_memory_decision(
        decision_type="episode_persisted",
        details={
            "episode_id": episode_id,
            "status": status,
            "strategy_profile_id": strategy_profile_id,
            "strategy_name": strategy_name,
            "plan_query_mix": plan_mix,
        },
        project_id=project_id,
        phase="terminal",
        strategy_profile_id=strategy_profile_id,
        confidence=0.8,
    )
    if strategy_profile_id:
        mem.record_graph_edge(
            edge_type="used_in",
            from_node_type="strategy_profile",
            from_node_id=strategy_profile_id,
            to_node_type="run_episode",
            to_node_id=episode_id,
            project_id=project_id,
        )
    question = str(project.get("question") or "")
    read_urls_list = []
    for sf in (proj_dir / "sources").glob("*.json"):
        if sf.name.endswith("_content.json"):
            continue
        if not (proj_dir / "sources" / (sf.stem + "_content.json")).exists():
            continue
        try:
            u = (json.loads(sf.read_text()).get("url") or "").strip()
            if u and "://" in u:
                read_urls_list.append(u)
        except Exception:
            pass
    if read_urls_list:
        mem.record_read_urls(question, read_urls_list)
MEMORY_V2_EPISODE
}

# Phase C: Conductor as master when RESEARCH_USE_CONDUCTOR=1 (bash pipeline remains fallback when 0)
if [ "${RESEARCH_USE_CONDUCTOR:-0}" = "1" ] && [ -f "$TOOLS/research_conductor.py" ]; then
  if python3 "$TOOLS/research_conductor.py" run_cycle "$PROJECT_ID" 2>> "$CYCLE_LOG"; then
    log "Conductor run_cycle completed."
    echo "done"
    exit 0
  fi
  log "Conductor run_cycle failed or incomplete — falling back to bash pipeline."
fi

# Shadow conductor: log what conductor would decide at this phase (no execution control)
if [ -f "$TOOLS/research_conductor.py" ] && [ "${RESEARCH_USE_CONDUCTOR:-0}" != "1" ]; then
  python3 "$TOOLS/research_conductor.py" shadow "$PROJECT_ID" "$PHASE" >> "$PROJ_DIR/conductor_shadow.log" 2>> "$CYCLE_LOG" || true
fi

case "$PHASE" in
  explore)
    log "Phase: EXPLORE — 3-round adaptive planning/search/read/coverage"
    progress_start "explore"

    # Core 10: token governor lane for this phase (tools may read RESEARCH_GOVERNOR_LANE or governor_lane.json)
    if [ "${RESEARCH_ENABLE_TOKEN_GOVERNOR:-0}" = "1" ]; then
      GOVERNOR_LANE=$(python3 -c "import sys; sys.path.insert(0,'$OPERATOR_ROOT'); from tools.research_token_governor import recommend_lane; print(recommend_lane('$PROJECT_ID'))" 2>/dev/null || echo "mid")
      export RESEARCH_GOVERNOR_LANE="${GOVERNOR_LANE:-mid}"
      echo "\"$GOVERNOR_LANE\"" > "$PROJ_DIR/governor_lane.json" 2>/dev/null || true
    fi

    # Core 10: prior knowledge and question graph before planner (Welle 1)
    if [ "${RESEARCH_ENABLE_KNOWLEDGE_SEED:-0}" = "1" ]; then
      python3 "$TOOLS/research_knowledge_seed.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    if [ "${RESEARCH_ENABLE_QUESTION_GRAPH:-0}" = "1" ]; then
      python3 "$TOOLS/research_question_graph.py" build "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi

    progress_step "Creating research plan"
    log "Starting: research_planner"
    timeout 300 python3 "$TOOLS/research_planner.py" "$QUESTION" "$PROJECT_ID" > "$ART/research_plan.json" 2>> "$CYCLE_LOG" || true
    if [ ! -s "$ART/research_plan.json" ]; then
      echo '{"queries":[],"topics":[],"complexity":"moderate"}' > "$ART/research_plan.json"
      log "Planner failed or timed out — using minimal plan"
    fi
    log "Done: research_planner"
    cp "$ART/research_plan.json" "$PROJ_DIR/research_plan.json"

    QUERY_COUNT=$(python3 -c "import json; d=json.load(open('$ART/research_plan.json')); print(len(d.get('queries',[])), end='')" 2>/dev/null || echo "0")
    COMPLEXITY=$(python3 -c "import json; d=json.load(open('$ART/research_plan.json')); print(d.get('complexity','moderate'), end='')" 2>/dev/null || echo "moderate")
    READ_LIMIT=$(python3 -c "c='$COMPLEXITY'; print(40 if c=='complex' else 25 if c=='moderate' else 15, end='')")

    progress_step "Searching $QUERY_COUNT targeted queries"
    python3 "$TOOLS/research_web_search.py" --queries-file "$ART/research_plan.json" --max-per-query 5 > "$ART/web_search_round1.json" 2>> "$CYCLE_LOG" || true

    # Core 10: academic sources into URL pool (Welle 1)
    if [ "${RESEARCH_ENABLE_ACADEMIC:-0}" = "1" ]; then
      mkdir -p "$PROJ_DIR/sources"
      python3 "$TOOLS/research_academic.py" semantic_scholar "$QUESTION" --max 5 > "$ART/academic_round1.json" 2>> "$CYCLE_LOG" || true
      if [ -s "$ART/academic_round1.json" ]; then
        python3 - "$PROJ_DIR" "$ART/academic_round1.json" <<'MERGE_ACADEMIC' 2>> "$CYCLE_LOG" || true
import json, sys, hashlib
from pathlib import Path
proj_dir, path = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(path.read_text()) if path.exists() else []
for item in (data if isinstance(data, list) else []):
    url = (item.get("url") or "").strip()
    if not url: continue
    fid = hashlib.sha256(url.encode()).hexdigest()[:12]
    out = dict(item)
    out.setdefault("title", out.get("abstract", "")[:200])
    out.setdefault("description", out.get("abstract", ""))
    out["confidence"] = 0.5
    out["source_quality"] = "academic"
    (proj_dir / "sources" / f"{fid}.json").write_text(json.dumps(out))
MERGE_ACADEMIC
      fi
    fi

    python3 - "$PROJ_DIR" "$ART/research_plan.json" "$ART/web_search_round1.json" <<'FILTER_AND_SAVE'
import json, sys, hashlib, re
from pathlib import Path
proj_dir = Path(sys.argv[1]); plan_path = Path(sys.argv[2]); search_path = Path(sys.argv[3])
plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}
results = json.loads(search_path.read_text()) if search_path.exists() else []
q_terms = set()
for q in plan.get("queries", []):
    qq = str(q.get("query","")).lower()
    for t in re.findall(r"[a-z0-9\-\+]{3,}", qq):
        q_terms.add(t)
for e in plan.get("entities", []):
    for t in re.findall(r"[a-z0-9\-\+]{3,}", str(e).lower()):
        q_terms.add(t)
topic_ids = {str(t.get("id","")) for t in plan.get("topics", [])}
saved = 0
for item in (results if isinstance(results, list) else []):
    url = (item.get("url") or "").strip()
    if not url:
        continue
    title_desc = f"{item.get('title','')} {item.get('description','')} {item.get('abstract','')}".lower()
    has_topic = str(item.get("topic_id","")) in topic_ids if topic_ids else False
    overlap = sum(1 for w in q_terms if w and w in title_desc)
    if not has_topic and overlap < 2:
        continue
    fid = hashlib.sha256(url.encode()).hexdigest()[:12]
    out = dict(item)
    out["confidence"] = float(out.get("confidence", 0.5))
    out["source_quality"] = out.get("source_quality", "unknown")
    (proj_dir / "sources" / f"{fid}.json").write_text(json.dumps(out))
    saved += 1
print(saved)
FILTER_AND_SAVE

    python3 - "$PROJ_DIR" "$ART/research_plan.json" "$ART" <<'SMART_RANK'
import json, os, sys, re
from pathlib import Path
proj_dir = Path(sys.argv[1]); plan = json.loads(Path(sys.argv[2]).read_text()); art = Path(sys.argv[3])
topics = {str(t.get("id","")): t for t in plan.get("topics", [])}
entities = [str(e).lower() for e in plan.get("entities", [])]
source_type_by_topic = {tid: set((t.get("source_types") or [])) for tid, t in topics.items()}
DOMAIN_RANK = {"arxiv.org":10,"semanticscholar.org":10,"nature.com":10,"science.org":10,"pubmed.ncbi.nlm.nih.gov":12,"ncbi.nlm.nih.gov":11,"nih.gov":11,"thelancet.com":11,"nejm.org":11,"bmj.com":10,"jamanetwork.com":10,"who.int":10,"cochranelibrary.com":10,"clinicaltrials.gov":10,"openai.com":9,"anthropic.com":9,"google.com":8,"reuters.com":8,"nytimes.com":8}
DOMAIN_BLOCKLIST = {"reddit.com","zenml.io","truefoundry.com","medium.com","quora.com"}
try:
    overrides = json.loads(os.environ.get("RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON", "{}"))
    if isinstance(overrides, dict):
        for k, v in overrides.items():
            DOMAIN_RANK[str(k).replace("www.", "")] = int(v)
except Exception:
    pass
per_domain = {}
ranked = []
for f in (proj_dir / "sources").glob("*.json"):
    if f.name.endswith("_content.json"): continue
    try:
        d = json.loads(f.read_text())
    except Exception:
        continue
    url = (d.get("url") or "").strip()
    if not url: continue
    domain = url.split("/")[2].replace("www.","") if "://" in url else ""
    if domain in DOMAIN_BLOCKLIST: continue
    per_domain.setdefault(domain, 0)
    if per_domain[domain] >= 3:
        continue
    tid = str(d.get("topic_id",""))
    topic = topics.get(tid, {})
    priority = int(topic.get("priority", 3))
    prio_boost = {1: 30, 2: 15, 3: 5}.get(priority, 5)
    stypes = source_type_by_topic.get(tid, set())
    type_boost = 0
    if "paper" in stypes and ("arxiv" in domain or "semanticscholar" in domain or "pubmed" in domain or "ncbi" in domain):
        type_boost += 15
    text = f"{d.get('title','')} {d.get('description','')} {d.get('abstract','')}".lower()
    entity_boost = sum(3 for e in entities if e and e in text)
    domain_boost = DOMAIN_RANK.get(domain, 4)
    score = prio_boost + type_boost + entity_boost + domain_boost
    ranked.append((-score, domain, str(f)))
    per_domain[domain] += 1
ranked.sort()
(art / "read_order_round1.txt").write_text("\n".join(path for _, _, path in ranked))
SMART_RANK
    python3 - "$PROJ_DIR" "$ART" "$OPERATOR_ROOT" "$QUESTION" <<FILTER_READ_URLS 2>> "$CYCLE_LOG" || true
import json, sys
from pathlib import Path
proj_dir, art, op_root, question = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
sys.path.insert(0, str(op_root))
order_file = art / "read_order_round1.txt"
if not order_file.exists():
    sys.exit(0)
paths = [ln.strip() for ln in order_file.read_text().splitlines() if ln.strip()]
try:
    from lib.memory import Memory
    with Memory() as mem:
        skip_urls = mem.get_read_urls_for_question(question or "")
except Exception:
    skip_urls = set()
if not skip_urls:
    sys.exit(0)
filtered = []
for p in paths:
    path = Path(p)
    if not path.exists():
        continue
    try:
        u = (json.loads(path.read_text()).get("url") or "").strip()
        if u and u not in skip_urls:
            filtered.append(p)
    except Exception:
        filtered.append(p)
order_file.write_text("\n".join(filtered))
FILTER_READ_URLS

    log "Starting: parallel_reader explore (limit=$READ_LIMIT workers=8)"
    READ_STATS=$(python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" explore --input-file "$ART/read_order_round1.txt" --read-limit "$READ_LIMIT" --workers 8 2>> "$CYCLE_LOG" | tail -1)
    read_attempts=0
    read_successes=0
    [ -n "$READ_STATS" ] && read -r read_attempts read_successes <<< "$(echo "$READ_STATS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('read_attempts',0), d.get('read_successes',0))" 2>/dev/null)" 2>/dev/null || true
    log "Done: parallel_reader explore (attempts=$read_attempts successes=$read_successes)"
    SATURATION_DETECTED=0
    python3 "$TOOLS/research_saturation_check.py" "$PROJ_DIR" 2>> "$CYCLE_LOG" || SATURATION_DETECTED=1

    progress_step "Assessing source coverage"
    python3 "$TOOLS/research_coverage.py" "$PROJECT_ID" > "$ART/coverage_round1.json"
    cp "$ART/coverage_round1.json" "$PROJ_DIR/coverage_round1.json"
    COVERAGE_PASS=$(python3 -c "import json; print(json.load(open('$ART/coverage_round1.json')).get('pass', False), end='')" 2>/dev/null || echo "False")

    if [ "$COVERAGE_PASS" != "True" ]; then
      progress_step "Planner Round 2: precision queries"
      python3 "$TOOLS/research_planner.py" --refinement-queries "$ART/coverage_round1.json" "$PROJECT_ID" > "$ART/refinement_queries.json" 2>> "$CYCLE_LOG" || true
      REFINEMENT_COUNT=$(python3 -c "import json; d=json.load(open('$ART/refinement_queries.json')) if __import__('pathlib').Path('$ART/refinement_queries.json').exists() else {}; print(len(d.get('queries', [])), end='')" 2>/dev/null || echo "0")
      if [ "$REFINEMENT_COUNT" -gt 0 ] && [ "$SATURATION_DETECTED" != "1" ]; then
      python3 "$TOOLS/research_web_search.py" --queries-file "$ART/refinement_queries.json" --max-per-query 5 > "$ART/refinement_search.json" 2>> "$CYCLE_LOG" || true
      python3 - "$PROJ_DIR" "$ART/refinement_search.json" <<'SAVE_REFINEMENT'
import json, sys, hashlib
from pathlib import Path
proj_dir, in_path = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(in_path.read_text()) if in_path.exists() else []
for item in (data if isinstance(data, list) else []):
    u = (item.get("url") or "").strip()
    if not u: continue
    sid = hashlib.sha256(u.encode()).hexdigest()[:12]
    (proj_dir / "sources" / f"{sid}.json").write_text(json.dumps(item))
SAVE_REFINEMENT
      python3 -c "
import json
from pathlib import Path
p = Path('$ART/refinement_search.json')
urls = []
if p.exists():
    data = json.loads(p.read_text())
    for item in (data if isinstance(data, list) else []):
        u = (item.get('url') or '').strip()
        if u and u not in urls:
            urls.append(u)
Path('$ART/refinement_urls_to_read.txt').write_text('\n'.join(urls[:10]))
"
      if [ -s "$ART/refinement_urls_to_read.txt" ]; then
        progress_step "Reading refinement sources"
        python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" explore --input-file "$ART/refinement_urls_to_read.txt" --read-limit 10 --workers 8 2>> "$CYCLE_LOG" | tail -1 > /dev/null || true
      fi
    fi

      progress_step "Filling coverage gaps (Round 2)"
      python3 "$TOOLS/research_planner.py" --gap-fill "$ART/coverage_round1.json" "$PROJECT_ID" > "$ART/gap_queries.json"
      python3 "$TOOLS/research_web_search.py" --queries-file "$ART/gap_queries.json" --max-per-query 8 > "$ART/gap_search_round2.json" 2>> "$CYCLE_LOG" || true
      python3 - "$PROJ_DIR" "$ART/gap_search_round2.json" <<'SAVE_GAP'
import json, sys, hashlib
from pathlib import Path
proj_dir, in_path = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(in_path.read_text()) if in_path.exists() else []
for item in (data if isinstance(data, list) else []):
    u = (item.get("url") or "").strip()
    if not u: continue
    sid = hashlib.sha256(u.encode()).hexdigest()[:12]
    (proj_dir / "sources" / f"{sid}.json").write_text(json.dumps(item))
SAVE_GAP
      python3 -c "
import json
from pathlib import Path
p = Path('$ART/gap_search_round2.json')
urls = []
if p.exists():
    data = json.loads(p.read_text())
    for item in (data if isinstance(data, list) else []):
        u = (item.get('url') or '').strip()
        if u and u not in urls:
            urls.append(u)
Path('$ART/gap_urls_to_read.txt').write_text('\n'.join(urls[:10]))
"
      if [ -s "$ART/gap_urls_to_read.txt" ] && [ "$SATURATION_DETECTED" != "1" ]; then
        progress_step "Reading gap-fill sources"
        python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" explore --input-file "$ART/gap_urls_to_read.txt" --read-limit 10 --workers 8 2>> "$CYCLE_LOG" | tail -1 > /dev/null || true
      fi
      python3 "$TOOLS/research_coverage.py" "$PROJECT_ID" > "$ART/coverage_round2.json"
      cp "$ART/coverage_round2.json" "$PROJ_DIR/coverage_round2.json"

      THIN_TOPICS=$(python3 -c "import json; d=json.load(open('$ART/coverage_round2.json')) if __import__('pathlib').Path('$ART/coverage_round2.json').exists() else json.load(open('$ART/coverage_round1.json')); print(json.dumps(d.get('thin_priority_topics', [])), end='')" 2>/dev/null || echo "[]")
      if [ "$THIN_TOPICS" != "[]" ]; then
        progress_step "Deep-diving thin topics (Round 3)"
        echo "$THIN_TOPICS" > "$ART/thin_topics.json"
        python3 "$TOOLS/research_planner.py" --perspective-rotate "$ART/thin_topics.json" "$PROJECT_ID" > "$ART/depth_queries.json"
        python3 "$TOOLS/research_web_search.py" --queries-file "$ART/depth_queries.json" --max-per-query 5 > "$ART/depth_search_round3.json" 2>> "$CYCLE_LOG" || true
        python3 - "$PROJ_DIR" "$ART/depth_search_round3.json" <<'SAVE_DEPTH'
import json, sys, hashlib
from pathlib import Path
proj_dir, in_path = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(in_path.read_text()) if in_path.exists() else []
for item in (data if isinstance(data, list) else []):
    u = (item.get("url") or "").strip()
    if not u: continue
    sid = hashlib.sha256(u.encode()).hexdigest()[:12]
    (proj_dir / "sources" / f"{sid}.json").write_text(json.dumps(item))
SAVE_DEPTH
        python3 -c "
import json
from pathlib import Path
p = Path('$ART/depth_search_round3.json')
urls = []
if p.exists():
    data = json.loads(p.read_text())
    for item in (data if isinstance(data, list) else []):
        u = (item.get('url') or '').strip()
        if u and u not in urls:
            urls.append(u)
Path('$ART/depth_urls_to_read.txt').write_text('\n'.join(urls[:8]))
"
        if [ -s "$ART/depth_urls_to_read.txt" ] && [ "$SATURATION_DETECTED" != "1" ]; then
          progress_step "Reading depth sources"
          python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" explore --input-file "$ART/depth_urls_to_read.txt" --read-limit 8 --workers 8 2>> "$CYCLE_LOG" | tail -1 > /dev/null || true
        fi
        python3 "$TOOLS/research_coverage.py" "$PROJECT_ID" > "$ART/coverage_round3.json"
        cp "$ART/coverage_round3.json" "$PROJ_DIR/coverage_round3.json"
      fi
    else
      log "Coverage passed after Round 1 — skipping Rounds 2-3"
    fi

    progress_step "Extracting findings"
    log "Starting: research_deep_extract"
    timeout 600 python3 "$TOOLS/research_deep_extract.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    log "Done: research_deep_extract"
    # Persist read stats for evidence gate and UI (research_quality_gate._load_explore_stats)
    read_failures=$((read_attempts - read_successes))
    mkdir -p "$PROJ_DIR/explore"
    python3 -c "
import json
from pathlib import Path
p = Path('$PROJ_DIR/explore/read_stats.json')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({
    'read_attempts': $read_attempts,
    'read_successes': $read_successes,
    'read_failures': $read_failures,
}, indent=2))
"
    # Core 10: post-read relevance gate, context compression, dynamic outline (Welle 1–2)
    if [ "${RESEARCH_ENABLE_RELEVANCE_GATE:-0}" = "1" ]; then
      python3 "$TOOLS/research_relevance_gate.py" batch "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    if [ "${RESEARCH_ENABLE_CONTEXT_MANAGER:-0}" = "1" ]; then
      python3 "$TOOLS/research_context_manager.py" add "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    if [ "${RESEARCH_ENABLE_DYNAMIC_OUTLINE:-0}" = "1" ]; then
      python3 "$TOOLS/research_dynamic_outline.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    advance_phase "focus"
    ;;
  focus)
    log "Phase: FOCUS — targeted deep-dive from coverage gaps"
    progress_start "focus"
    if [ "${RESEARCH_ENABLE_TOKEN_GOVERNOR:-0}" = "1" ]; then
      GOVERNOR_LANE=$(python3 -c "import sys; sys.path.insert(0,'$OPERATOR_ROOT'); from tools.research_token_governor import recommend_lane; print(recommend_lane('$PROJECT_ID'))" 2>/dev/null || echo "mid")
      export RESEARCH_GOVERNOR_LANE="${GOVERNOR_LANE:-mid}"
      echo "\"$GOVERNOR_LANE\"" > "$PROJ_DIR/governor_lane.json" 2>/dev/null || true
    fi
    progress_step "Analyzing coverage gaps"
    # Coverage is copied to PROJ_DIR by explore; use it when FOCUS runs in a separate job
    COV_FILE="$PROJ_DIR/coverage_round3.json"
    [ -f "$COV_FILE" ] || COV_FILE="$PROJ_DIR/coverage_round2.json"
    [ -f "$COV_FILE" ] || COV_FILE="$PROJ_DIR/coverage_round1.json"
    [ -f "$COV_FILE" ] || COV_FILE="$ART/coverage_round3.json"
    [ -f "$COV_FILE" ] || COV_FILE="$ART/coverage_round2.json"
    [ -f "$COV_FILE" ] || COV_FILE="$ART/coverage_round1.json"
    if [ ! -f "$COV_FILE" ]; then
      log "No coverage file found (explore may have run in another job) — using empty focus queries"
      echo '{"queries":[]}' > "$ART/focus_queries.json"
    else
      python3 "$TOOLS/research_planner.py" --gap-fill "$COV_FILE" "$PROJECT_ID" > "$ART/focus_queries.json"
    fi
    progress_step "Searching for sources (KI)"
    python3 "$TOOLS/research_web_search.py" --queries-file "$ART/focus_queries.json" --max-per-query 8 > "$ART/focus_search.json" 2>> "$CYCLE_LOG" || true
    progress_step "Saving and ranking sources"
    python3 - "$PROJ_DIR" "$ART/focus_search.json" <<'FOCUS_SAVE'
import json, sys, hashlib
from pathlib import Path
proj_dir, src = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(src.read_text()) if src.exists() else []
for item in (data if isinstance(data, list) else []):
    url = (item.get("url") or "").strip()
    if not url:
        continue
    sid = hashlib.sha256(url.encode()).hexdigest()[:12]
    (proj_dir / "sources" / f"{sid}.json").write_text(json.dumps(item))
FOCUS_SAVE

    python3 - "$PROJ_DIR" "$ART/focus_queries.json" "$ART" <<'RANK_FOCUS'
import json, os, sys
from pathlib import Path
proj_dir, qpath, art = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
plan = json.loads(qpath.read_text()) if qpath.exists() else {}
topic_boost = {}
for i, q in enumerate(plan.get("queries", [])):
    tid = str(q.get("topic_id",""))
    if tid not in topic_boost:
        topic_boost[tid] = max(1, 10 - i)
DOMAIN_RANK = {"arxiv.org":10,"semanticscholar.org":10,"nature.com":10,"science.org":10,"pubmed.ncbi.nlm.nih.gov":12,"ncbi.nlm.nih.gov":11,"nih.gov":11,"thelancet.com":11,"nejm.org":11,"bmj.com":10,"jamanetwork.com":10,"who.int":10,"cochranelibrary.com":10,"clinicaltrials.gov":10,"openai.com":9,"anthropic.com":9,"reuters.com":8,"nytimes.com":8}
DOMAIN_BLOCKLIST = {"reddit.com","zenml.io","truefoundry.com","medium.com","quora.com"}
try:
    overrides = json.loads(os.environ.get("RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON", "{}"))
    if isinstance(overrides, dict):
        for k, v in overrides.items():
            DOMAIN_RANK[str(k).replace("www.", "")] = int(v)
except Exception:
    pass
ranked = []
for f in (proj_dir / "sources").glob("*.json"):
    if f.name.endswith("_content.json"): continue
    sid = f.stem
    if (proj_dir / "sources" / f"{sid}_content.json").exists(): continue
    try:
        d = json.loads(f.read_text())
    except Exception:
        continue
    url = (d.get("url") or "").strip()
    if not url: continue
    domain = url.split("/")[2].replace("www.","") if "://" in url else ""
    if domain in DOMAIN_BLOCKLIST: continue
    score = DOMAIN_RANK.get(domain, 4) + topic_boost.get(str(d.get("topic_id","")), 0)
    ranked.append((-score, str(f)))
ranked.sort()
(art / "focus_read_order.txt").write_text("\n".join(path for _, path in ranked))
RANK_FOCUS
    FOCUS_STATS=$(python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" focus --input-file "$ART/focus_read_order.txt" --read-limit 15 --workers 8 2>> "$CYCLE_LOG" | tail -1)
    focus_read_attempts=0
    focus_read_successes=0
    [ -n "$FOCUS_STATS" ] && read -r focus_read_attempts focus_read_successes <<< "$(echo "$FOCUS_STATS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('read_attempts',0), d.get('read_successes',0))" 2>/dev/null)" 2>/dev/null || true
    log "Focus reads: $focus_read_attempts attempted, $focus_read_successes succeeded"
    progress_step "Extracting focused findings"
    timeout 600 python3 "$TOOLS/research_deep_extract.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    if [ "${RESEARCH_ENABLE_CONTEXT_MANAGER:-0}" = "1" ]; then
      python3 "$TOOLS/research_context_manager.py" add "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    progress_done
    advance_phase "connect"
    ;;
  connect)
    progress_start "connect"
    source "$OPERATOR_ROOT/workflows/research/phases/connect.sh"
    ;;
  verify)
    log "Phase: VERIFY — source reliability, claim verification, fact-check"
    progress_start "verify"
    progress_step "Checking source reliability"
    if ! timeout 300 python3 "$TOOLS/research_verify.py" "$PROJECT_ID" source_reliability > "$ART/source_reliability.json" 2>> "$CYCLE_LOG"; then
      log "source_reliability failed — retrying in 30s"
      sleep 30
      timeout 300 python3 "$TOOLS/research_verify.py" "$PROJECT_ID" source_reliability > "$ART/source_reliability.json" 2>> "$CYCLE_LOG" || true
    fi
    progress_step "Verifying claims"
    if ! timeout 300 python3 "$TOOLS/research_verify.py" "$PROJECT_ID" claim_verification > "$ART/claim_verification.json" 2>> "$CYCLE_LOG"; then
      log "claim_verification failed — retrying in 30s"
      sleep 30
      timeout 300 python3 "$TOOLS/research_verify.py" "$PROJECT_ID" claim_verification > "$ART/claim_verification.json" 2>> "$CYCLE_LOG" || true
    fi
    if ! timeout 300 python3 "$TOOLS/research_verify.py" "$PROJECT_ID" fact_check > "$ART/fact_check.json" 2>> "$CYCLE_LOG"; then
      log "fact_check failed — retrying in 30s"
      sleep 30
      timeout 300 python3 "$TOOLS/research_verify.py" "$PROJECT_ID" fact_check > "$ART/fact_check.json" 2>> "$CYCLE_LOG" || true
    fi
    # Persist verify artifacts to project for synthesize phase (only copy non-empty files)
    mkdir -p "$PROJ_DIR/verify"
    [ -s "$ART/source_reliability.json" ] && cp "$ART/source_reliability.json" "$PROJ_DIR/verify/" 2>/dev/null || true
    [ -s "$ART/claim_verification.json" ] && cp "$ART/claim_verification.json" "$PROJ_DIR/verify/" 2>/dev/null || true
    [ -s "$ART/fact_check.json" ] && cp "$ART/fact_check.json" "$PROJ_DIR/verify/" 2>/dev/null || true
    # Claim ledger: deterministic is_verified (V3)
    progress_step "Building claim ledger"
    timeout 300 python3 "$TOOLS/research_verify.py" "$PROJECT_ID" claim_ledger > "$ART/claim_ledger.json" 2>> "$CYCLE_LOG" || true
    [ -s "$ART/claim_ledger.json" ] && cp "$ART/claim_ledger.json" "$PROJ_DIR/verify/" 2>/dev/null || true
    # Core 10: AEM claim state machine, contradiction linking, falsification gate (Welle 3)
    if [ "${RESEARCH_ENABLE_CLAIM_STATE_MACHINE:-0}" = "1" ]; then
      python3 "$TOOLS/research_claim_state_machine.py" upgrade "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    if [ "${RESEARCH_ENABLE_CONTRADICTION_LINKING:-0}" = "1" ]; then
      python3 "$TOOLS/research_contradiction_linking.py" run "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    if [ "${RESEARCH_ENABLE_FALSIFICATION_GATE:-0}" = "1" ]; then
      python3 "$TOOLS/research_falsification_gate.py" run "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    # Counter-evidence: search for contradicting sources for top 3 verified claims (before gate)
    python3 - "$PROJ_DIR" "$ART" "$TOOLS" "$OPERATOR_ROOT" <<'COUNTER_EVIDENCE' 2>> "$CYCLE_LOG" || true
import json, sys, hashlib, subprocess
from pathlib import Path
proj_dir, art, tools, op_root = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
verify_dir = proj_dir / "verify"
claims_data = []
for f in ["claim_ledger.json", "claim_verification.json"]:
    p = verify_dir / f
    if p.exists():
        try:
            data = json.loads(p.read_text())
            claims_data = data.get("claims", data.get("claims", []))
            break
        except Exception:
            pass
verified = [c for c in claims_data if c.get("is_verified") or c.get("verified")][:3]
counter_queries = []
for c in verified:
    claim_text = (c.get("text") or c.get("claim") or "")[:80].strip()
    if not claim_text:
        continue
    counter_queries.append(f'"{claim_text}" disputed OR incorrect OR false OR misleading')
    counter_queries.append(f'{claim_text} criticism OR rebuttal OR different numbers')
counter_queries = counter_queries[:6]
for i, q in enumerate(counter_queries):
    out = art / f"counter_search_{i}.json"
    try:
        r = subprocess.run([sys.executable, str(tools / "research_web_search.py"), q, "--max", "3"],
                          capture_output=True, text=True, timeout=60, cwd=str(op_root))
        if r.stdout and r.stdout.strip():
            out.write_text(r.stdout)
    except Exception:
        pass
# Merge counter results into sources and collect URLs to read
existing_urls = set()
for f in (proj_dir / "sources").glob("*.json"):
    if f.name.endswith("_content.json"):
        continue
    try:
        u = json.loads(f.read_text()).get("url", "").strip()
        if u:
            existing_urls.add(u)
    except Exception:
        pass
urls_to_read = []
for i in range(6):
    f = art / f"counter_search_{i}.json"
    if not f.exists():
        continue
    try:
        data = json.loads(f.read_text())
        for item in (data if isinstance(data, list) else []):
            url = (item.get("url") or "").strip()
            if not url or url in existing_urls:
                continue
            existing_urls.add(url)
            fid = hashlib.sha256(url.encode()).hexdigest()[:12]
            (proj_dir / "sources" / f"{fid}.json").write_text(json.dumps({**item, "confidence": 0.5, "source_quality": "counter"}))
            urls_to_read.append(url)
    except Exception:
        pass
(art / "counter_urls_to_read.txt").write_text("\n".join(urls_to_read[:9]))
COUNTER_EVIDENCE
    if [ -f "$ART/counter_urls_to_read.txt" ] && [ -s "$ART/counter_urls_to_read.txt" ]; then
      python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" counter --input-file "$ART/counter_urls_to_read.txt" --read-limit 9 --workers 8 2>> "$CYCLE_LOG" | tail -1 > /dev/null || true
      python3 "$TOOLS/research_reason.py" "$PROJECT_ID" contradiction_detection > "$PROJ_DIR/contradictions.json" 2>> "$CYCLE_LOG" || true
    fi
    # Evidence Gate: must pass before synthesize
    GATE_RESULT=$(timeout 300 python3 "$TOOLS/research_quality_gate.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || echo '{"pass":false}')
    if ! GATE_PASS=$(echo "$GATE_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(1 if d.get('pass') else 0, end='')" 2>/dev/null); then GATE_PASS=0; fi
    if [ "$GATE_PASS" != "1" ]; then
      # Smart recovery: if unread sources remain and recovery not yet attempted, read more and re-gate
      UNREAD_COUNT=$(python3 -c "
from pathlib import Path
sources = Path('$PROJ_DIR/sources')
unread = [f for f in sources.glob('*.json')
          if not f.name.endswith('_content.json')
          and not (sources / (f.stem + '_content.json')).exists()]
print(len(unread), end='')" 2>/dev/null) || UNREAD_COUNT=0
      RECOVERY_MARKER="$PROJ_DIR/verify/.recovery_attempted"
      if [ "$UNREAD_COUNT" -gt 0 ] && [ ! -f "$RECOVERY_MARKER" ]; then
        log "Evidence gate failed but $UNREAD_COUNT unread sources — attempting recovery reads"
        mkdir -p "$PROJ_DIR/verify"
        touch "$RECOVERY_MARKER"
        # Rank unread sources and read up to 10
        python3 - "$PROJ_DIR" "$QUESTION" "$ART" <<'RANK_RECOVERY'
import json, sys, re
from pathlib import Path
proj_dir, question, art = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
q_words = set(re.sub(r'[^a-z0-9 ]', '', question.lower()).split())
q_words = {w for w in q_words if len(w) >= 4}
DOMAIN_RANK = {"nytimes.com":10,"reuters.com":10,"theverge.com":9,"arstechnica.com":9,"techcrunch.com":9,"fortune.com":8,"axios.com":8}
ranked = []
for f in (proj_dir / "sources").glob("*.json"):
    if f.name.endswith("_content.json"): continue
    sid = f.stem
    if (proj_dir / "sources" / f"{sid}_content.json").exists(): continue
    try:
        d = json.loads(f.read_text())
        url = (d.get("url") or "").strip()
        if not url: continue
        domain = url.split("/")[2].replace("www.","") if len(url.split("/")) > 2 else ""
        dscore = DOMAIN_RANK.get(domain, 5)
        td = f"{d.get('title','')} {d.get('description','')}".lower()
        relevance = sum(1 for w in q_words if w in td)
        ranked.append((-(dscore * 10 + relevance), str(f)))
    except Exception:
        pass
ranked.sort()
(art / "recovery_read_order.txt").write_text("\n".join(path for _, path in ranked))
RANK_RECOVERY
        RECOVERY_STATS=$(python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" recovery --input-file "$ART/recovery_read_order.txt" --read-limit 10 --workers 8 2>> "$CYCLE_LOG" | tail -1)
        recovery_reads=0
        recovery_successes=0
        [ -n "$RECOVERY_STATS" ] && read -r recovery_reads recovery_successes <<< "$(echo "$RECOVERY_STATS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('read_attempts',0), d.get('read_successes',0))" 2>/dev/null)" 2>/dev/null || true
        log "Recovery reads: $recovery_reads attempted, $recovery_successes succeeded"
        if [ "$recovery_successes" -gt 0 ]; then
          # Re-run claim verification and ledger with new findings
          timeout 300 python3 "$TOOLS/research_verify.py" "$PROJECT_ID" claim_verification > "$ART/claim_verification.json" 2>> "$CYCLE_LOG" || true
          [ -s "$ART/claim_verification.json" ] && cp "$ART/claim_verification.json" "$PROJ_DIR/verify/" 2>/dev/null || true
          timeout 300 python3 "$TOOLS/research_verify.py" "$PROJECT_ID" claim_ledger > "$ART/claim_ledger.json" 2>> "$CYCLE_LOG" || true
          [ -s "$ART/claim_ledger.json" ] && cp "$ART/claim_ledger.json" "$PROJ_DIR/verify/" 2>/dev/null || true
          # Re-check evidence gate
          GATE_RESULT=$(timeout 300 python3 "$TOOLS/research_quality_gate.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || echo '{"pass":false}')
          if ! GATE_PASS=$(echo "$GATE_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(1 if d.get('pass') else 0, end='')" 2>/dev/null); then GATE_PASS=0; fi
          log "Recovery gate result: GATE_PASS=$GATE_PASS"
        fi
      fi
    fi
    if [ "$GATE_PASS" != "1" ]; then
      GATE_DECISION=$(echo "$GATE_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('decision','fail'), end='')" 2>/dev/null) || GATE_DECISION="fail"
      if [ "$GATE_DECISION" = "pending_review" ]; then
        log "Evidence gate: pending_review — awaiting human approval"
        python3 - "$PROJ_DIR" "$GATE_RESULT" <<'PENDING_REVIEW'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
proj_dir, gate_str = Path(sys.argv[1]), sys.argv[2]
try:
  gate = json.loads(gate_str)
except Exception:
  gate = {"decision": "pending_review", "metrics": {}, "reasons": []}
d = json.loads((proj_dir / "project.json").read_text())
d["status"] = "pending_review"
d.setdefault("quality_gate", {})["evidence_gate"] = {
  "status": "pending_review",
  "decision": "pending_review",
  "fail_code": None,
  "metrics": gate.get("metrics", {}),
  "reasons": gate.get("reasons", []),
}
d["quality_gate"]["last_evidence_gate_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
(proj_dir / "project.json").write_text(json.dumps(d, indent=2))
PENDING_REVIEW
        exit 0
      fi
      # decision == "fail": try gap-driven loop-back to focus (max 2)
      python3 "$TOOLS/research_reason.py" "$PROJECT_ID" gap_analysis > "$ART/gaps_verify.json" 2>> "$CYCLE_LOG" || true
      LOOP_BACK=$(python3 - "$PROJ_DIR" "$ART" <<'LOOPCHECK'
import json, sys
from pathlib import Path
proj_dir, art = Path(sys.argv[1]), Path(sys.argv[2])
d = json.loads((proj_dir / "project.json").read_text())
gaps = []
if (art / "gaps_verify.json").exists():
  try:
    gaps = json.loads((art / "gaps_verify.json").read_text()).get("gaps", [])
  except Exception:
    pass
high_gaps = [g for g in gaps if g.get("priority") == "high"]
phase_history = d.get("phase_history", [])
loopback_count = phase_history.count("focus")
if high_gaps and loopback_count < 2:
  queries = [g.get("suggested_search", "").strip() for g in high_gaps[:5] if g.get("suggested_search", "").strip()]
  if queries:
    (proj_dir / "verify").mkdir(parents=True, exist_ok=True)
    (proj_dir / "verify" / "deepening_queries.json").write_text(json.dumps({"queries": queries}, indent=2))
  print("1" if queries else "0", end="")
else:
  print("0", end="")
LOOPCHECK
)
      if [ "$LOOP_BACK" = "1" ]; then
        log "Evidence gate failed but high-priority gaps found — looping back to focus (deepening)"
        advance_phase "focus"
        exit 0
      fi
      log "Evidence gate failed — not advancing to synthesize"
      python3 - "$PROJ_DIR" "$GATE_RESULT" <<'GATE_FAIL'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
proj_dir, gate_str = Path(sys.argv[1]), sys.argv[2]
try:
  gate = json.loads(gate_str)
except Exception:
  gate = {"fail_code": "failed_insufficient_evidence", "decision": "fail", "metrics": {}, "reasons": []}
d = json.loads((proj_dir / "project.json").read_text())
d["status"] = gate.get("fail_code") or "failed_insufficient_evidence"
d["phase"] = "failed"
d.setdefault("quality_gate", {})["evidence_gate"] = {
  "status": "failed",
  "decision": gate.get("decision", "fail"),
  "fail_code": gate.get("fail_code"),
  "metrics": gate.get("metrics", {}),
  "reasons": gate.get("reasons", []),
}
d["quality_gate"]["last_evidence_gate_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
d["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
(proj_dir / "project.json").write_text(json.dumps(d, indent=2))
GATE_FAIL
      # Generate abort report from existing data (zero LLM cost)
      python3 "$TOOLS/research_abort_report.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
      log "Abort report generated for $PROJECT_ID"
      # Brain/Memory reflection after failed run (non-fatal)
      python3 - "$PROJ_DIR" "$OPERATOR_ROOT" "$PROJECT_ID" <<'BRAIN_REFLECT' 2>> "$CYCLE_LOG" || true
import json, sys
from pathlib import Path
proj_dir, op_root, project_id = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(op_root))
try:
    d = json.loads((proj_dir / "project.json").read_text())
    metrics = {"project_id": project_id, "status": d.get("status"), "phase": d.get("phase"), "spend": d.get("current_spend", 0), "phase_timings": d.get("phase_timings", {})}
    metrics["findings_count"] = len(list((proj_dir / "findings").glob("*.json")))
    metrics["source_count"] = len([f for f in (proj_dir / "sources").glob("*.json") if "_content" not in f.name])
    from lib.memory import Memory
    mem = Memory()
    mem.record_episode("research_complete", f"Research {project_id} finished: {d.get('status')} | {metrics['findings_count']} findings", metadata=metrics)
    gate_metrics = d.get("quality_gate", {}).get("evidence_gate", {}).get("metrics", {})
    quality_proxy = gate_metrics.get("claim_support_rate", 0.0)
    mem.record_quality(job_id=project_id, score=float(quality_proxy), workflow_id="research-cycle", notes=f"gate_fail | {metrics['findings_count']} findings, {metrics['source_count']} sources")
    mem.record_project_outcome(project_id=project_id, domain=d.get("domain"), critic_score=float(quality_proxy), user_verdict="none", gate_metrics_json=json.dumps(gate_metrics), findings_count=metrics["findings_count"], source_count=metrics["source_count"])
    mem.close()
except Exception as e:
    print(f"[brain] reflection failed (non-fatal): {e}", file=sys.stderr)
BRAIN_REFLECT
      python3 "$TOOLS/research_experience_distiller.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
      python3 "$TOOLS/research_utility_update.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
      persist_v2_episode "failed"
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
d.setdefault("quality_gate", {})["evidence_gate"] = {"status": "passed", "decision": gate.get("decision", "pass"), "metrics": gate.get("metrics", {}), "reasons": []}
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
    # Update source credibility from verify outcomes (per-domain)
    python3 "$TOOLS/research_source_credibility.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    # AEM Settlement (optional; when contracts present): upgrade ledger, run settlement, write AEM artifacts.
    # Enforcement: observe=fail-open; enforce=block if AEM fails; strict=block if AEM fails or oracle_integrity_rate < 0.80.
    AEM_ADVANCE=1
    if [ -f "$TOOLS/research_claim_outcome_schema.py" ] && [ -f "$TOOLS/research_episode_metrics.py" ]; then
      progress_step "AEM settlement"
      python3 "$TOOLS/research_aem_settlement.py" "$PROJECT_ID" > "$ART/aem_result.json" 2>> "$CYCLE_LOG"
      AEM_EXIT=$?
      AEM_MODE="${AEM_ENFORCEMENT_MODE:-observe}"
      if [ "$AEM_MODE" = "enforce" ] || [ "$AEM_MODE" = "strict" ]; then
        AEM_ADVANCE=$(python3 -c "
import json, os
art = os.environ.get('ART', '$ART')
mode = os.environ.get('AEM_ENFORCEMENT_MODE', 'observe').strip().lower() or 'observe'
path = os.path.join(art, 'aem_result.json')
advance = 1
try:
    with open(path) as f:
        d = json.load(f)
    ok = d.get('ok', True)
    block = d.get('block_synthesize', False)
    if mode == 'enforce' and not ok:
        advance = 0
    elif mode == 'strict' and (not ok or block):
        advance = 0
except Exception:
    if mode != 'observe':
        advance = 0
print(advance)
" ART="$ART" AEM_ENFORCEMENT_MODE="${AEM_ENFORCEMENT_MODE:-observe}" 2>/dev/null) || AEM_ADVANCE=0
      fi
      if [ "$AEM_ADVANCE" = "0" ]; then
        log "AEM block: mode=$AEM_MODE AEM_EXIT=$AEM_EXIT — not advancing to synthesize"
        python3 - "$PROJ_DIR" "$ART" "$AEM_MODE" "$AEM_EXIT" <<'AEM_BLOCK'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
proj_dir, art, mode, aem_exit = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], int(sys.argv[4])
reason = f"aem_blocked mode={mode} exit={aem_exit}"
try:
    p = art / "aem_result.json"
    if p.exists():
        d = json.loads(p.read_text())
        if d.get("block_synthesize"):
            reason = "aem_blocked oracle_integrity_rate_below_threshold"
        elif not d.get("ok"):
            reason = "aem_blocked settlement_failed"
except Exception:
    pass
d = json.loads((proj_dir / "project.json").read_text())
d["status"] = "aem_blocked"
d["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
d.setdefault("quality_gate", {})["aem_block_reason"] = reason
(proj_dir / "project.json").write_text(json.dumps(d, indent=2))
AEM_BLOCK
        exit 0
      fi
    fi
    # Discovery Analysis (only in discovery mode, after evidence gate passes)
    FM=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print((d.get('config') or {}).get('research_mode', 'standard'), end='')" 2>/dev/null || echo "standard")
    if [ "$FM" = "discovery" ]; then
      progress_step "Running Discovery Analysis"
      python3 "$TOOLS/research_discovery_analysis.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    # Evidence gate passed — advance to synthesize (no loop-back; gate already enforces evidence)
    advance_phase "synthesize"
    fi
    ;;
  synthesize)
    log "Phase: SYNTHESIZE — report"
    progress_start "synthesize"
    progress_step "Generating outline"
    export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
    # Multi-pass section-by-section synthesis (research-firm-grade report)
    timeout 900 python3 "$TOOLS/research_synthesize.py" "$PROJECT_ID" > "$ART/report.md" 2>> "$CYCLE_LOG" || true
    progress_step "Saving report & applying citations"
    python3 - "$PROJ_DIR" "$ART" "$OPERATOR_ROOT" <<'PY'
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone
proj_dir, art, op_root = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
verify_dir = proj_dir / "verify"
report = ""
if (art / "report.md").exists():
  report = (art / "report.md").read_text()
ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
sys.path.insert(0, str(op_root))
from tools.research_common import get_claims_for_synthesis
claim_ledger = get_claims_for_synthesis(proj_dir)
from tools.research_verify import apply_verified_tags_to_report
report = apply_verified_tags_to_report(report, claim_ledger)
# Deterministic References section (replaces LLM-generated sources list)
import re as _re
# Strip any LLM-generated References/Sources section at end of report
report = _re.sub(
    r'\n---\s*\n\*?\*?(?:Sources|References)\*?\*?:?\s*\n.*',
    '', report, flags=_re.DOTALL | _re.IGNORECASE
).rstrip()
report = _re.sub(
    r'\n#+\s*(?:Sources|References)\s*\n.*',
    '', report, flags=_re.DOTALL | _re.IGNORECASE
).rstrip()

# Collect unique URLs with titles from findings + source metadata
ref_map = {}  # url -> title
for fp in sorted((proj_dir / "findings").glob("*.json")):
    try:
        fd = json.loads(fp.read_text())
        fu = (fd.get("url") or "").strip()
        if fu and fu not in ref_map:
            ref_map[fu] = (fd.get("title") or "").strip()
    except Exception:
        pass
for sp in sorted((proj_dir / "sources").glob("*.json")):
    if "_content" in sp.name:
        continue
    try:
        sd = json.loads(sp.read_text())
        su = (sd.get("url") or "").strip()
        if su and su not in ref_map:
            ref_map[su] = (sd.get("title") or "").strip()
    except Exception:
        pass

# Only include sources that appear in claim_ledger
cited_urls = set()
for c in claim_ledger:
    for u in c.get("supporting_source_ids", []):
        cited_urls.add(u.strip())
refs = [(u, ref_map.get(u, "")) for u in cited_urls if u in ref_map]
refs.sort(key=lambda r: r[1] or r[0])

if refs:
    report += "\n\n---\n\n## References\n\n"
    for i, (url, title) in enumerate(refs, 1):
        if title:
            report += f"[{i}] {title}  \n    {url}\n\n"
        else:
            report += f"[{i}] {url}\n\n"
(art / "report.md").write_text(report)
(proj_dir / "reports" / f"report_{ts}.md").write_text(report)
# Audit: claim_evidence_map per report (include verification_reason for UI: verified/disputed/unverified)
# Build URL -> excerpt index from findings
findings_by_url = {}
for fp in sorted((proj_dir / "findings").glob("*.json")):
    try:
        fd = json.loads(fp.read_text())
        fu = (fd.get("url") or "").strip()
        if fu and fd.get("excerpt"):
            findings_by_url.setdefault(fu, fd["excerpt"][:500])
    except Exception:
        pass

# Also try source metadata (title+description) as fallback snippet
for sp in sorted((proj_dir / "sources").glob("*.json")):
    if "_content" in sp.name:
        continue
    try:
        sd = json.loads(sp.read_text())
        su = (sd.get("url") or "").strip()
        if su and su not in findings_by_url:
            snippet = (sd.get("description") or sd.get("title") or "")[:300]
            if snippet:
                findings_by_url[su] = snippet
    except Exception:
        pass

claim_evidence_map = {"report_id": f"report_{ts}.md", "ts": ts, "claims": []}
for c in claim_ledger:
    evidence = []
    for src_url in c.get("supporting_source_ids", []):
        snippet = findings_by_url.get(src_url, "")
        evidence.append({"url": src_url, "snippet": snippet})
    claim_evidence_map["claims"].append({
        "claim_id": c.get("claim_id"),
        "text": (c.get("text") or "")[:500],
        "is_verified": c.get("is_verified"),
        "verification_reason": c.get("verification_reason"),
        "supporting_source_ids": c.get("supporting_source_ids", []),
        "supporting_evidence": evidence,
    })
(proj_dir / "reports" / f"claim_evidence_map_{ts}.json").write_text(json.dumps(claim_evidence_map, indent=2))
(proj_dir / "verify" / "claim_evidence_map_latest.json").write_text(json.dumps(claim_evidence_map, indent=2))
# Generate report manifest
manifest_entries = []
for rpt in sorted((proj_dir / "reports").glob("report_*.md"), key=lambda p: p.stat().st_mtime):
  name = rpt.name
  rpt_ts = name.replace("report_", "").replace("_revised.md", "").replace(".md", "")
  is_revised = "_revised" in name
  critique_score = None
  critique_file = proj_dir / "verify" / "critique.json"
  if critique_file.exists():
    try:
      critique_score = json.loads(critique_file.read_text()).get("score")
    except Exception:
      pass
  manifest_entries.append({
    "filename": name,
    "generated_at": rpt_ts,
    "is_revised": is_revised,
    "quality_score": critique_score,
    "path": f"research/{proj_dir.name}/reports/{name}",
    "is_final": False,
  })
# Last report is final (updated after Critic via MANIFEST_UPDATE for quality_score)
if manifest_entries:
  manifest_entries[-1]["is_final"] = True
(proj_dir / "reports" / "manifest.json").write_text(json.dumps({
  "project_id": proj_dir.name,
  "report_count": len(manifest_entries),
  "reports": manifest_entries,
  "pipeline": {
    "synthesis_model": os.environ.get("RESEARCH_SYNTHESIS_MODEL", "unknown"),
    "critique_model": os.environ.get("RESEARCH_CRITIQUE_MODEL", "unknown"),
    "verify_model": os.environ.get("RESEARCH_VERIFY_MODEL", "unknown"),
    "gate_thresholds": {
      "hard_pass_verified_min": 5,
      "soft_pass_verified_min": 3,
      "review_zone_rate": 0.4,
    },
  },
}, indent=2))
PY
    # Quality Gate: critic pass; up to 2 revision rounds if score below threshold
    # Default 0.50 so typical ~0.55 scores pass; frontier = explicit low bar.
    CRITIC_THRESHOLD="${RESEARCH_CRITIC_THRESHOLD:-0.50}"
    if [ -n "${RESEARCH_MEMORY_CRITIC_THRESHOLD:-}" ]; then
      CRITIC_THRESHOLD="$RESEARCH_MEMORY_CRITIC_THRESHOLD"
    fi
    FM=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print((d.get('config') or {}).get('research_mode', 'standard'), end='')" 2>/dev/null || echo "standard")
    if [ "$FM" = "frontier" ]; then
      CRITIC_THRESHOLD="0.50"
    fi
    MAX_REVISE_ROUNDS="${RESEARCH_MEMORY_REVISE_ROUNDS:-2}"
    progress_step "Running quality critic"
    timeout 600 python3 "$TOOLS/research_critic.py" "$PROJECT_ID" critique "$ART" > "$ART/critique.json" 2>> "$CYCLE_LOG" || true
    if [ ! -s "$ART/critique.json" ]; then
      log "Critic output empty — retrying in 15s"
      sleep 15
      timeout 600 python3 "$TOOLS/research_critic.py" "$PROJECT_ID" critique "$ART" > "$ART/critique.json" 2>> "$CYCLE_LOG" || true
    fi
    [ -s "$ART/critique.json" ] && cp "$ART/critique.json" "$PROJ_DIR/verify/" 2>/dev/null || true
    SCORE=0.5
    if [ -f "$ART/critique.json" ]; then
      SCORE=$(python3 -c "import json; d=json.load(open('$ART/critique.json')); print(d.get('score', 0.5), end='')" 2>/dev/null || echo "0.5")
    fi
    FORCE_ONE_REVISION=0
    if [ -f "$ART/critique.json" ]; then
      FORCE_ONE_REVISION=$(python3 -c "
import json
try:
  d = json.load(open('$ART/critique.json'))
  weaknesses = d.get('weaknesses') or []
  text = ' '.join(str(w) for w in weaknesses).lower()
  if any(k in text for k in ['unvollständig', 'bricht ab', 'fehlt']):
    print('1', end='')
  else:
    print('0', end='')
except Exception:
  print('0', end='')
" 2>/dev/null) || FORCE_ONE_REVISION=0
    fi
    REV_ROUND=0
    while [ "$REV_ROUND" -lt "$MAX_REVISE_ROUNDS" ]; do
      NEED_REVISION=0
      if python3 -c "exit(0 if float('$SCORE') < float('$CRITIC_THRESHOLD') else 1)" 2>/dev/null; then NEED_REVISION=1; fi
      if [ "$FORCE_ONE_REVISION" = "1" ] && [ "$REV_ROUND" -eq 0 ]; then NEED_REVISION=1; fi
      [ "$NEED_REVISION" -eq 0 ] && break
      REV_ROUND=$((REV_ROUND + 1))
      if [ "$FORCE_ONE_REVISION" = "1" ] && [ "$REV_ROUND" -eq 1 ]; then
        log "Critic found critical structural weaknesses — forcing at least one revision round."
      else
        log "Report quality below threshold (score $SCORE, threshold $CRITIC_THRESHOLD). Revision round $REV_ROUND/$MAX_REVISE_ROUNDS..."
      fi
      timeout 600 python3 "$TOOLS/research_critic.py" "$PROJECT_ID" revise "$ART" > "$ART/revised_report.md" 2>> "$CYCLE_LOG" || true
      if [ -f "$ART/revised_report.md" ] && [ -s "$ART/revised_report.md" ]; then
        cp "$ART/revised_report.md" "$ART/report.md"
        REV_TS=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'), end='')")
        cp "$ART/revised_report.md" "$PROJ_DIR/reports/report_${REV_TS}_revised${REV_ROUND}.md"
      fi
      timeout 600 python3 "$TOOLS/research_critic.py" "$PROJECT_ID" critique "$ART" > "$ART/critique.json" 2>> "$CYCLE_LOG" || true
      SCORE=$(python3 -c "import json; d=json.load(open('$ART/critique.json')); print(d.get('score', 0.5), end='')" 2>/dev/null || echo "0.5")
    done
    progress_step "Critic done — score: $SCORE"
    if python3 -c "exit(0 if float('$SCORE') < float('$CRITIC_THRESHOLD') else 1)" 2>/dev/null; then
      log "Quality gate failed (score $SCORE, threshold $CRITIC_THRESHOLD) — status failed_quality_gate"
      python3 - "$PROJ_DIR" "$ART" "$SCORE" <<'QF_FAIL'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
proj_dir, art, score = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
d = json.loads((proj_dir / "project.json").read_text())
d["status"] = "failed_quality_gate"
d["phase"] = "failed"
d.setdefault("quality_gate", {})["critic_score"] = score
d["quality_gate"]["quality_gate_status"] = "failed"
d["quality_gate"]["fail_code"] = "failed_quality_gate"
d["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
(proj_dir / "project.json").write_text(json.dumps(d, indent=2))
QF_FAIL
      python3 "$TOOLS/research_abort_report.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
      python3 - "$PROJ_DIR" "$OPERATOR_ROOT" "$PROJECT_ID" "$SCORE" <<'OUTCOME_RECORD' 2>> "$CYCLE_LOG" || true
import json, sys
from pathlib import Path
proj_dir, op_root, project_id, score = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], float(sys.argv[4])
sys.path.insert(0, str(op_root))
d = json.loads((proj_dir / "project.json").read_text())
try:
    from lib.memory import Memory
    mem = Memory()
    fc = len(list((proj_dir / "findings").glob("*.json")))
    sc = len([f for f in (proj_dir / "sources").glob("*.json") if "_content" not in f.name])
    gate_metrics = d.get("quality_gate", {}).get("evidence_gate", {}).get("metrics", {})
    mem.record_project_outcome(project_id=project_id, domain=d.get("domain"), critic_score=score, user_verdict="rejected", gate_metrics_json=json.dumps(gate_metrics), findings_count=fc, source_count=sc)
    mem.close()
except Exception as e:
    print(f"[outcome] failed (non-fatal): {e}", file=sys.stderr)
OUTCOME_RECORD
      python3 "$TOOLS/research_experience_distiller.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
      python3 "$TOOLS/research_utility_update.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
      persist_v2_episode "failed"
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
    # Manifest: set quality_score from critique after Critic block
    python3 - "$PROJ_DIR" <<'MANIFEST_UPDATE' 2>/dev/null || true
import json, sys
from pathlib import Path
proj_dir = Path(sys.argv[1])
manifest_path = proj_dir / "reports" / "manifest.json"
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text())
    critique_score = None
    critique_file = proj_dir / "verify" / "critique.json"
    if critique_file.exists():
        try:
            critique_score = json.loads(critique_file.read_text()).get("score")
        except Exception:
            pass
    for report in manifest.get("reports", []):
        if report.get("quality_score") is None and critique_score is not None:
            report["quality_score"] = critique_score
    manifest_path.write_text(json.dumps(manifest, indent=2))
MANIFEST_UPDATE
    # Generate PDF report (non-fatal)
    log "Generating PDF report..."
    progress_step "Generating final PDF"
    if ! python3 "$OPERATOR_ROOT/tools/research_pdf_report.py" "$PROJECT_ID" 2>> "$CYCLE_LOG"; then
      log "PDF generation failed (install weasyprint? pip install weasyprint); see log.txt for details"
    fi
    progress_step "PDF generated"
    # Store verified findings in Memory DB for cross-domain learning (non-fatal)
    python3 "$OPERATOR_ROOT/tools/research_embed.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    # Update cross-project links (Brain/UI can show cross-links)
    python3 "$TOOLS/research_cross_domain.py" --threshold 0.75 --max-pairs 20 2>> "$CYCLE_LOG" || true
    advance_phase "done"
    progress_done
    # Telegram: Forschung abgeschlossen (only when passed)
    if [ -x "$TOOLS/send-telegram.sh" ]; then
      MSG_FILE=$(mktemp)
      printf "Research abgeschlossen: %s\nFrage: %.200s\nReport: research/%s/reports/\n" "$PROJECT_ID" "$QUESTION" "$PROJECT_ID" >> "$MSG_FILE"
      "$TOOLS/send-telegram.sh" "$MSG_FILE" 2>/dev/null || true
      rm -f "$MSG_FILE"
    fi
    if [ "${RESEARCH_AUTO_FOLLOWUP:-0}" = "1" ] && [ -f "$TOOLS/research_auto_followup.py" ]; then
      python3 "$TOOLS/research_auto_followup.py" "$PROJECT_ID" >> "$CYCLE_LOG" 2>&1 || true
    fi
    # Brain/Memory reflection after successful run (non-fatal)
    python3 - "$PROJ_DIR" "$OPERATOR_ROOT" "$PROJECT_ID" <<'BRAIN_REFLECT' 2>> "$CYCLE_LOG" || true
import json, sys
from pathlib import Path
proj_dir, op_root, project_id = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(op_root))
try:
    d = json.loads((proj_dir / "project.json").read_text())
    metrics = {"project_id": project_id, "status": d.get("status"), "phase": d.get("phase"), "spend": d.get("current_spend", 0), "phase_timings": d.get("phase_timings", {})}
    metrics["findings_count"] = len(list((proj_dir / "findings").glob("*.json")))
    metrics["source_count"] = len([f for f in (proj_dir / "sources").glob("*.json") if "_content" not in f.name])
    metrics["read_success"] = len([f for f in (proj_dir / "sources").glob("*_content.json")])
    from lib.memory import Memory
    mem = Memory()
    mem.record_episode("research_complete", f"Research {project_id} finished: {d.get('status')} | {metrics['findings_count']} findings, {metrics['source_count']} sources", metadata=metrics)
    critic_score = d.get("quality_gate", {}).get("critic_score")
    if critic_score is not None:
        mem.record_quality(job_id=project_id, score=float(critic_score), workflow_id="research-cycle", notes=f"{metrics['findings_count']} findings, {metrics['source_count']} sources")
    gate_metrics = d.get("quality_gate", {}).get("evidence_gate", {}).get("metrics", {})
    mem.record_project_outcome(project_id=project_id, domain=d.get("domain"), critic_score=float(critic_score) if critic_score is not None else None, user_verdict="approved", gate_metrics_json=json.dumps(gate_metrics), findings_count=metrics["findings_count"], source_count=metrics["source_count"])
    mem.close()
except Exception as e:
    print(f"[brain] reflection failed (non-fatal): {e}", file=sys.stderr)
BRAIN_REFLECT
    python3 "$TOOLS/research_experience_distiller.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    python3 "$TOOLS/research_utility_update.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    persist_v2_episode "done"
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

echo "Phase $PHASE complete." >> "$CYCLE_LOG"
echo "done"
