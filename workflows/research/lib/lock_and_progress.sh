# Research phase: terminal status guard, project lock, progress helpers, EXIT trap.
# Expects: PROJ_DIR, PROJECT_ID, CYCLE_LOG, PHASE, log (from config.sh).

# Terminal status guard: if project is dead, don't run
_STATUS=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('status',''), end='')" 2>/dev/null || echo "")
case "$_STATUS" in
  failed*|cancelled|abandoned)
    log "Project $PROJECT_ID has terminal status '$_STATUS' — skipping cycle"
    exit 0
    ;;
esac

# Project-level lock: only one research-cycle per project at a time
CYCLE_LOCK="$PROJ_DIR/.cycle.lock"
_acquire_lock() {
  exec 9>"$CYCLE_LOCK"
  flock -n 9
}
if ! _acquire_lock; then
  exec 9>&-
  prev_pid=""
  progress_alive="true"
  [ -f "$PROJ_DIR/progress.json" ] && prev_pid=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/progress.json')); print(d.get('pid','') or '', end='')" 2>/dev/null) && progress_alive=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/progress.json')); print(str(d.get('alive', True)).lower(), end='')" 2>/dev/null)
  do_recover=0
  if [ -n "$prev_pid" ] && [ ! -d "/proc/$prev_pid" ]; then do_recover=1; fi
  if [ "$progress_alive" = "false" ]; then do_recover=1; fi
  if [ "$do_recover" -eq 1 ]; then
    rm -f "$CYCLE_LOCK"
    if _acquire_lock; then
      log "Recovered stale lock (pid=$prev_pid no longer alive or progress alive=false). Proceeding."
    else
      log "Another research-cycle is already running for $PROJECT_ID — skipping."
      exit 2
    fi
  else
    log "Another research-cycle is already running for $PROJECT_ID — skipping."
    exit 2
  fi
fi

PROGRESS_STARTED=0
PROGRESS_FINALIZED=0
progress_start() {
  PROGRESS_STARTED=1
  python3 "$TOOLS/research_progress.py" start "$PROJECT_ID" "$1" 2>/dev/null || true
}
progress_step() { python3 "$TOOLS/research_progress.py" step "$PROJECT_ID" "$1" "${2:-}" "${3:-}" 2>/dev/null || true; }
progress_done() {
  local phase="${1:-done}"
  local step_msg="${2:-}"
  PROGRESS_FINALIZED=1
  python3 "$TOOLS/research_progress.py" done "$PROJECT_ID" "$phase" "$step_msg" 2>/dev/null || true
}

finalize_progress_on_exit() {
  local exit_code="$?"
  if [ "${PROGRESS_STARTED:-0}" = "1" ] && [ "${PROGRESS_FINALIZED:-0}" != "1" ]; then
    local final_phase
    final_phase=$(python3 -c "import json; print(json.load(open('$PROJ_DIR/project.json')).get('phase','${PHASE:-explore}'), end='')" 2>/dev/null || echo "${PHASE:-explore}")
    progress_done "$final_phase" "Idle"
    log "Finalized progress on exit (code=$exit_code, phase=$final_phase)"
  fi
  rm -f "$CYCLE_LOCK" 2>/dev/null || true
}
trap finalize_progress_on_exit EXIT
