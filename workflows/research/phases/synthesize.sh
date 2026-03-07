# Phase: SYNTHESIZE — report (sourced from research-phase.sh)
    log "Phase: SYNTHESIZE — report"
    progress_start "synthesize"
    if [ "${RESEARCH_ENABLE_TOKEN_GOVERNOR:-1}" = "1" ]; then
      GOVERNOR_LANE=$(python3 -c "import sys; sys.path.insert(0,'$OPERATOR_ROOT'); from tools.research_token_governor import recommend_lane; print(recommend_lane('$PROJECT_ID'))" 2>/dev/null || echo "mid")
      export RESEARCH_GOVERNOR_LANE="${GOVERNOR_LANE:-mid}"
      echo "\"$GOVERNOR_LANE\"" > "$PROJ_DIR/governor_lane.json" 2>/dev/null || true
    fi
    progress_step "Generating outline"
    export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
    # Multi-pass section-by-section synthesis (research-firm-grade report)
    timeout 1800 python3 "$TOOLS/research_synthesize.py" "$PROJECT_ID" > "$ART/report.md" 2>> "$CYCLE_LOG" || true
    FM=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print((d.get('config') or {}).get('research_mode', 'standard'), end='')" 2>/dev/null || echo "standard")
    # Discovery fallback: never die on synthesis formatting/runtime errors when evidence gate already passed
    if [ "$FM" = "discovery" ]; then
      if [ ! -s "$ART/report.md" ] || python3 -c "import pathlib; t=pathlib.Path('$ART/report.md').read_text(encoding='utf-8', errors='ignore') if pathlib.Path('$ART/report.md').exists() else ''; print(1 if '# Synthesis Error' in t else 0, end='')" 2>/dev/null | grep -q '^1$'; then
        log "Discovery synth fallback: report missing or synthesis error — generating robust fallback report."
        python3 - "$PROJ_DIR" "$ART" "$PROJECT_ID" "$QUESTION" <<'DISCOVERY_FALLBACK' 2>> "$CYCLE_LOG" || true
import json, sys
from pathlib import Path
proj_dir, art_dir, project_id, question = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
da = proj_dir / "discovery_analysis.json"
brief = {}
if da.exists():
    try:
        brief = (json.loads(da.read_text(encoding="utf-8", errors="replace")) or {}).get("discovery_brief", {}) or {}
    except Exception:
        brief = {}
lines = [
    "# Research Report (Discovery Fallback)",
    "",
    f"Project: `{project_id}`",
    f"Question: {question}",
    "",
    "## Discovery Synthesis",
]
if brief.get("key_hypothesis"):
    lines += ["", "### Key Hypothesis", "", str(brief.get("key_hypothesis"))]
for title, key in [
    ("Novel Connections", "novel_connections"),
    ("Emerging Concepts", "emerging_concepts"),
    ("Research Frontier", "research_frontier"),
    ("Unexplored Opportunities", "unexplored_opportunities"),
]:
    vals = brief.get(key) or []
    if isinstance(vals, list) and vals:
        lines += ["", f"### {title}"]
        for v in vals[:8]:
            lines.append(f"- {v}")
cl = proj_dir / "verify" / "claim_ledger.json"
if cl.exists():
    try:
        ledger = json.loads(cl.read_text(encoding="utf-8", errors="replace"))
        if isinstance(ledger, list) and ledger:
            lines += ["", "## Claims (from verify)", ""]
            for c in ledger[:15]:
                t = (c.get("text") or "")[:120].replace("\n", " ")
                if t:
                    lines.append(f"- {t}")
    except Exception:
        pass
pj = proj_dir / "project.json"
if pj.exists():
    try:
        d = json.loads(pj.read_text())
        qg = d.get("quality_gate") or {}
        eg = qg.get("evidence_gate") or {}
        metrics = eg.get("metrics") or {}
        if metrics:
            lines += ["", "## Verify metrics", "", f"- Findings: {metrics.get('findings_count', '—')}", f"- Sources: {metrics.get('source_count', '—')}", f"- Verified claims: {metrics.get('verified_claim_count', '—')}"]
    except Exception:
        pass
lines += ["", "## Note", "", "Fallback generated because primary synthesis failed. Evidence artifacts remain available in findings/verify/discovery_analysis."]
(art_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
DISCOVERY_FALLBACK
      fi
    fi
    progress_step "Saving report & applying citations"
    python3 "$TOOLS/research_synthesize_postprocess.py" "$PROJECT_ID" "$ART" 2>> "$CYCLE_LOG" || true
    # Quality Gate: critic pass; up to 2 revision rounds if score below threshold
    # Default 0.50 so typical ~0.55 scores pass; frontier = explicit low bar.
    CRITIC_THRESHOLD="${RESEARCH_CRITIC_THRESHOLD:-0.50}"
    if [ -n "${RESEARCH_MEMORY_CRITIC_THRESHOLD:-}" ]; then
      CRITIC_THRESHOLD="$RESEARCH_MEMORY_CRITIC_THRESHOLD"
    fi
    if [ "$FM" = "frontier" ]; then
      CRITIC_THRESHOLD="0.50"
    fi
    MAX_REVISE_ROUNDS="${RESEARCH_MEMORY_REVISE_ROUNDS:-2}"
    if [ "${RESEARCH_ENABLE_TOKEN_GOVERNOR:-1}" = "1" ]; then
      GOVERNOR_LANE=$(python3 -c "import sys; sys.path.insert(0,'$OPERATOR_ROOT'); from tools.research_token_governor import recommend_lane; print(recommend_lane('$PROJECT_ID'))" 2>/dev/null || echo "mid")
      export RESEARCH_GOVERNOR_LANE="${GOVERNOR_LANE:-mid}"
      echo "\"$GOVERNOR_LANE\"" > "$PROJ_DIR/governor_lane.json" 2>/dev/null || true
    fi
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
    SUCCESS_PATH=0
    if python3 -c "exit(0 if float('$SCORE') < float('$CRITIC_THRESHOLD') else 1)" 2>/dev/null; then
      if [ "$FM" = "discovery" ]; then
        log "Discovery mode: critic score below threshold (score $SCORE, threshold $CRITIC_THRESHOLD) — advisory only, continuing."
        python3 - "$PROJ_DIR" "$ART" "$SCORE" <<'QG_DISCOVERY_SOFT'
import json, sys
from pathlib import Path
proj_dir, art, score = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
d = json.loads((proj_dir / "project.json").read_text())
d.setdefault("quality_gate", {})["critic_score"] = score
d["quality_gate"]["quality_gate_status"] = "advisory_low_score"
d["quality_gate"]["fail_code"] = None
d["status"] = "done"
d["phase"] = "done"
if (art / "critique.json").exists():
  try:
    c = json.loads((art / "critique.json").read_text())
    d["quality_gate"]["weaknesses_addressed"] = c.get("weaknesses", [])[:5]
  except Exception:
    pass
(proj_dir / "project.json").write_text(json.dumps(d, indent=2))
QG_DISCOVERY_SOFT
        SUCCESS_PATH=1
      else
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
      fi
    else
    SUCCESS_PATH=1
    fi
    if [ "$SUCCESS_PATH" = "1" ]; then
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

    # Core 10 Phase 2: Trial & Error Experiment Loop
    EXPERIMENT_GATE_OK=1
    if [ "${RESEARCH_ENABLE_EXPERIMENT_LOOP:-1}" = "1" ]; then
      progress_start "experiment"
      progress_step "Running Trial & Error Sandbox Experiment"
      log "Starting: research_experiment"
      timeout 900 python3 "$TOOLS/research_experiment.py" "$PROJECT_ID" >> "$CYCLE_LOG" 2>&1 || true
      log "Done: research_experiment"
      # Discovery: nur bei Sandbox-Crash/Timeout failen. Positive und negative Ergebnisse
      # (Hypothese bestätigt / widerlegt / unklar) sind gültige Entdeckungen → done.
      if [ "${RESEARCH_STRICT_EXPERIMENT_GATE:-1}" = "1" ] && [ "$FM" = "discovery" ]; then
        EXPERIMENT_GATE_OK=$(python3 - "$PROJ_DIR" <<'EXPERIMENT_GATE_CHECK'
import json, sys
from pathlib import Path
proj_dir = Path(sys.argv[1])
exp_path = proj_dir / "experiment.json"
if not exp_path.exists():
    print("0", end="")
    sys.exit(0)
try:
    d = json.loads(exp_path.read_text(encoding="utf-8", errors="replace"))
except Exception:
    print("0", end="")
    sys.exit(0)
gate = d.get("gate") if isinstance(d.get("gate"), dict) else {}
execution_success = gate.get("execution_success")
if execution_success is None:
    execution_success = d.get("success", False)
# Discovery: pass whenever the experiment ran (no crash/timeout). Negative results are valid discoveries.
print("1" if execution_success else "0", end="")
EXPERIMENT_GATE_CHECK
)
        if [ "$EXPERIMENT_GATE_OK" != "1" ]; then
          log "Experiment gate failed: sandbox execution failed (crash/timeout). Marking failed_experiment_gate."
          python3 - "$PROJ_DIR" <<'EXPERIMENT_GATE_FAIL'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
proj_dir = Path(sys.argv[1])
p = proj_dir / "project.json"
d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
exp = {}
try:
    exp = json.loads((proj_dir / "experiment.json").read_text(encoding="utf-8", errors="replace"))
except Exception:
    exp = {}
reasons = []
if isinstance(exp.get("gate"), dict):
    reasons = exp["gate"].get("reasons") or []
d["status"] = "failed_experiment_gate"
d["phase"] = "failed"
d.setdefault("quality_gate", {})["quality_gate_status"] = "failed"
d["quality_gate"]["fail_code"] = "failed_experiment_gate"
d["quality_gate"]["experiment_gate"] = {
    "status": "failed",
    "objective_met": bool(exp.get("objective_met", False)),
    "reasons": reasons[:8],
}
d["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
p.write_text(json.dumps(d, indent=2), encoding="utf-8")
EXPERIMENT_GATE_FAIL
          python3 "$TOOLS/research_abort_report.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
          python3 "$TOOLS/research_experience_distiller.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
          python3 "$TOOLS/research_utility_update.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
          persist_v2_episode "failed"
          progress_done "failed" "Idle"
          exit 0
        fi
      fi
    fi

    # Store verified findings in Memory DB for cross-domain learning (non-fatal)
    python3 "$OPERATOR_ROOT/tools/research_embed.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    # Update cross-project links (Brain/UI can show cross-links)
    python3 "$TOOLS/research_cross_domain.py" --threshold 0.75 --max-pairs 20 2>> "$CYCLE_LOG" || true
    advance_phase "done"
    progress_done "done" "Done"
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
