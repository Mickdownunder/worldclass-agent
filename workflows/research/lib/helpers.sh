# Research phase helpers: log_v2_mode_for_cycle, advance_phase, mark_waiting_next_cycle, persist_v2_episode.
# Expects: PROJ_DIR, PROJECT_ID, ART, TOOLS, OPERATOR_ROOT, CYCLE_LOG, PHASE, log, progress_*.

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

advance_phase() {
  local next_phase="$1"
  log "advance_phase: requesting $next_phase"
  if [ -f "$TOOLS/research_conductor.py" ] && [ "${RESEARCH_CONDUCTOR_GATE:-1}" != "0" ] && [ "${RESEARCH_USE_CONDUCTOR:-0}" != "1" ]; then
    local conductor_next
    conductor_next=$(python3 "$TOOLS/research_conductor.py" gate "$PROJECT_ID" "$next_phase" 2>> "$CYCLE_LOG") || true
    conductor_next="${conductor_next:-}"
    if [ -z "${conductor_next// }" ]; then
      log "Conductor gate returned empty — not advancing; keeping current phase"
      next_phase=$(python3 -c "import json; print(json.load(open('$PROJ_DIR/project.json')).get('phase','explore'), end='')" 2>> "$CYCLE_LOG") || next_phase="$1"
    elif [ "$conductor_next" != "$next_phase" ]; then
      if [ "$next_phase" = "focus" ] && [ "$conductor_next" = "explore" ] && [ "${RESEARCH_CONDUCTOR_ALLOW_EXPLORE_OVERRIDE_ON_COVERAGE_PASS:-0}" != "1" ]; then
        local override_allowed
        override_allowed=$(python3 - "$PROJ_DIR" <<'PY_GUARD'
import json, sys
from pathlib import Path
proj = Path(sys.argv[1])
# Discovery: never allow focus->explore when we have discovery evidence bar (6 findings, 4 sources)
try:
    d = json.loads((proj / "project.json").read_text())
    config = d.get("config") or {}
    if (config.get("research_mode") or "").strip().lower() == "discovery":
        findings_count = len(list((proj / "findings").glob("*.json")))
        source_count = len([f for f in (proj / "sources").glob("*.json") if not f.name.endswith("_content.json")])
        if findings_count >= 6 and source_count >= 4:
            print("0", end="")  # block override: enough evidence for discovery
            raise SystemExit(0)
except Exception:
    pass
coverage_pass = False
for name in ("coverage_round3.json", "coverage_round2.json", "coverage_round1.json"):
    p = proj / name
    if not p.exists():
        continue
    try:
        d = json.loads(p.read_text())
        if bool(d.get("pass")):
            coverage_pass = True
            break
    except Exception:
        pass
findings_count = len(list((proj / "findings").glob("*.json")))
source_count = len([f for f in (proj / "sources").glob("*.json") if not f.name.endswith("_content.json")])
allow = (not coverage_pass) or findings_count < 8 or source_count < 20
print("1" if allow else "0", end="")
PY_GUARD
)
        if [ "$override_allowed" = "1" ]; then
          log "Conductor override allowed (focus -> explore): evidence still thin."
          log "Conductor override: $next_phase -> $conductor_next (re-running phase)"
          next_phase="$conductor_next"
          progress_step "Conductor: weitere ${next_phase}-Runde"
          export RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1
        else
          log "Conductor override blocked: focus -> explore denied after coverage/evidence threshold reached."
        fi
      else
        log "Conductor override: $next_phase -> $conductor_next (re-running phase)"
        next_phase="$conductor_next"
        progress_step "Conductor: weitere ${next_phase}-Runde"
        export RESEARCH_ADVANCE_SKIP_LOOP_LIMIT=1
      fi
    fi
  fi
  python3 "$TOOLS/research_advance_phase.py" "$PROJ_DIR" "$next_phase"
  if [ "$next_phase" != "$1" ]; then
    progress_start "$next_phase"
    log "advance_phase: progress updated to phase=$next_phase for UI"
  fi
  unset -v RESEARCH_ADVANCE_SKIP_LOOP_LIMIT 2>/dev/null || true
  log "advance_phase: set phase=$next_phase"
}

mark_waiting_next_cycle() {
  python3 - "$PROJ_DIR" <<'WAITING_NEXT_CYCLE'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
proj_dir = Path(sys.argv[1])
p = proj_dir / "project.json"
try:
    d = json.loads(p.read_text())
except Exception:
    raise SystemExit(0)
status = str(d.get("status") or "").strip().lower()
phase = str(d.get("phase") or "").strip().lower()
terminal = (
    phase in {"done", "failed"}
    or status in {"done", "cancelled", "abandoned", "pending_review", "aem_blocked"}
    or status.startswith("failed")
)
if terminal:
    raise SystemExit(0)
d["status"] = "waiting_next_cycle"
d["last_cycle_completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
d["waiting_reason"] = f"Phase '{phase or 'unknown'}' prepared. Waiting for next research-cycle run."
p.write_text(json.dumps(d, indent=2))
WAITING_NEXT_CYCLE
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
