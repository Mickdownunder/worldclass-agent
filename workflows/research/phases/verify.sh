    log "Phase: VERIFY — source reliability, claim verification, fact-check"
    progress_start "verify"
    if [ "${RESEARCH_ENABLE_TOKEN_GOVERNOR:-1}" = "1" ]; then
      GOVERNOR_LANE=$(python3 -c "import sys; sys.path.insert(0,'$OPERATOR_ROOT'); from tools.research_token_governor import recommend_lane; print(recommend_lane('$PROJECT_ID'))" 2>/dev/null || echo "mid")
      export RESEARCH_GOVERNOR_LANE="${GOVERNOR_LANE:-mid}"
      echo "\"$GOVERNOR_LANE\"" > "$PROJ_DIR/governor_lane.json" 2>/dev/null || true
    fi
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
    # CoVe (Phase 3): independent verification when enabled (fail-safe: never upgrades, only downgrades)
    if [ "${RESEARCH_ENABLE_COVE_VERIFICATION:-0}" = "1" ]; then
      progress_step "CoVe claim verification"
      timeout 120 python3 "$TOOLS/research_verify.py" "$PROJECT_ID" claim_verification_cove 2>> "$CYCLE_LOG" || true
    fi
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
        RECOVERY_STATS=$(python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" recovery --input-file "$ART/recovery_read_order.txt" --read-limit 10 --workers "$WORKERS" 2>> "$CYCLE_LOG" | tail -1)
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
  # Phase 4: structured deepening_queries (query, reason, priority) for Focus merge
  queries = []
  for g in high_gaps[:5]:
    q = (g.get("suggested_search") or "").strip()
    if not q:
      continue
    queries.append({
      "query": q[:200],
      "reason": (g.get("description") or "")[:300],
      "priority": g.get("priority") or "high",
    })
  if queries:
    (proj_dir / "verify").mkdir(parents=True, exist_ok=True)
    (proj_dir / "verify" / "deepening_queries.json").write_text(json.dumps({"queries": queries}, indent=2, ensure_ascii=False))
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
        persist_v2_episode "aem_blocked"
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
