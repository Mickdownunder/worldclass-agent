#!/usr/bin/env bash
# Run one phase of the research cycle for a project. Request = project_id.
# Phases: explore -> focus -> connect -> verify -> synthesize -> done
# Refactored: config, lock/progress, helpers in workflows/research/lib/; phases in workflows/research/phases/.
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
export OPERATOR_ROOT

# Config: paths, env, phase, memory strategy (sets TOOLS, RESEARCH, ART, PROJ_DIR, PROJECT_ID, PHASE, QUESTION, log, ...)
source "$OPERATOR_ROOT/workflows/research/lib/config.sh"
log "Cycle started: project=$PROJECT_ID phase=$PHASE"
# Lock and progress: terminal status guard, project lock, progress_*, EXIT trap
source "$OPERATOR_ROOT/workflows/research/lib/lock_and_progress.sh"
# Helpers: advance_phase, mark_waiting_next_cycle, persist_v2_episode, log_v2_mode_for_cycle
source "$OPERATOR_ROOT/workflows/research/lib/helpers.sh"

# So UI does not show "Waiting for next cycle" while this run is active
if [ "$PHASE" != "done" ]; then
  python3 - "$PROJ_DIR" "$PHASE" <<'SET_ACTIVE' 2>/dev/null || true
import json, sys
from pathlib import Path
proj_dir, phase = Path(sys.argv[1]), sys.argv[2]
p = proj_dir / "project.json"
if not p.exists():
    sys.exit(0)
d = json.loads(p.read_text())
s = (d.get("status") or "").strip()
if s in ("done", "cancelled", "abandoned", "pending_review", "aem_blocked") or (s or "").startswith("failed"):
    sys.exit(0)
d["status"] = "active"
d.pop("waiting_reason", None)
p.write_text(json.dumps(d, indent=2))
SET_ACTIVE
fi

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

# Phase C: Conductor as master when RESEARCH_USE_CONDUCTOR=1 (bash pipeline remains fallback when 0)
if [ "${RESEARCH_USE_CONDUCTOR:-0}" = "1" ] && [ -f "$TOOLS/research_conductor.py" ]; then
  if python3 "$TOOLS/research_conductor.py" run_cycle "$PROJECT_ID" 2>> "$CYCLE_LOG"; then
    log "Conductor run_cycle completed."
    echo "done"
    exit 0
  fi
  log "Conductor run_cycle failed or incomplete — falling back to bash pipeline."
  CURR_STATUS=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('status',''), end='')" 2>> "$CYCLE_LOG") || true
  if [ "$CURR_STATUS" = "failed_conductor_tool_errors" ]; then
    persist_v2_episode "failed"
    exit 0
  fi
fi

# Shadow conductor: log what conductor would decide at this phase (no execution control)
if [ -f "$TOOLS/research_conductor.py" ] && [ "${RESEARCH_USE_CONDUCTOR:-0}" != "1" ]; then
  python3 "$TOOLS/research_conductor.py" shadow "$PROJECT_ID" "$PHASE" >> "$PROJ_DIR/conductor_shadow.log" 2>> "$CYCLE_LOG" || true
fi

case "$PHASE" in
  explore)
    source "$OPERATOR_ROOT/workflows/research/phases/explore.sh"
    ;;
  focus)
    source "$OPERATOR_ROOT/workflows/research/phases/focus.sh"
    ;;
  connect)
    progress_start "connect"
    source "$OPERATOR_ROOT/workflows/research/phases/connect.sh"
    ;;
  verify)
    source "$OPERATOR_ROOT/workflows/research/phases/verify.sh"
    ;;
  synthesize)
    source "$OPERATOR_ROOT/workflows/research/phases/synthesize.sh"
    ;;
  done)
    log "Project already done."
    ;;
  *)
    log "Unknown phase: $PHASE; setting to explore"
    advance_phase "explore"
    ;;
esac

# Check if this completion triggers a Council Meeting
STATUS=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('status',''), end='')" 2>/dev/null || echo "")
PHASE_NOW=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('phase',''), end='')" 2>/dev/null || echo "$PHASE")
FM_FINAL=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print((d.get('config') or {}).get('research_mode', 'standard'), end='')" 2>/dev/null || echo "standard")

# One cycle run usually advances exactly one phase. Mark explicit waiting state so UI
# does not look "stuck" when no process is running between phase runs.
mark_waiting_next_cycle
STATUS=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('status',''), end='')" 2>/dev/null || echo "$STATUS")

TRIGGER_COUNCIL=0
if [ "$FM_FINAL" = "discovery" ]; then
  # Discovery policy: Council only from successful parent completion
  if [ "$STATUS" = "done" ] || [ "$PHASE_NOW" = "done" ] || [ "$PHASE" = "done" ]; then
    TRIGGER_COUNCIL=1
  fi
else
  if [ "$PHASE" = "done" ] || [ "$PHASE_NOW" = "done" ] || [ "$STATUS" = "done" ] || [[ "$PHASE" == failed* ]] || [[ "$STATUS" == failed* ]] || [ "$STATUS" = "aem_blocked" ]; then
    TRIGGER_COUNCIL=1
  fi
fi
if [ "$TRIGGER_COUNCIL" = "1" ]; then
  python3 "$OPERATOR_ROOT/tools/trigger_council.py" "$PROJECT_ID" >> "$CYCLE_LOG" 2>&1 || true
fi

# Emit one structured completion event instead of ad-hoc file signals or direct Brain launches.
python3 "$OPERATOR_ROOT/tools/research_control_event.py" research-cycle-completed "$PROJECT_ID"   --completed-phase "$PHASE"   --resulting-phase "$PHASE_NOW"   --resulting-status "$STATUS"   --research-mode "$FM_FINAL"   --council-triggered "$TRIGGER_COUNCIL" >> "$CYCLE_LOG" 2>&1 || true
log "Emitted control-plane completion event for project=$PROJECT_ID completed_phase=$PHASE resulting_phase=$PHASE_NOW status=$STATUS"

echo "Phase $PHASE complete." >> "$CYCLE_LOG"
echo "done"
