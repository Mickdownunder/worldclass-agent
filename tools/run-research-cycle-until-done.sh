#!/usr/bin/env bash
# Run research-cycle repeatedly until project phase is "done".
# Usage: run-research-cycle-until-done.sh <project_id>
# Example: ./run-research-cycle-until-done.sh proj-20260225-654f85b2
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
# Discovery: do not fail run when experiment sandbox crashes/times out; treat as valid outcome and continue to done
export RESEARCH_STRICT_EXPERIMENT_GATE="${RESEARCH_STRICT_EXPERIMENT_GATE:-0}"
RUN_SINGLE_CYCLE="$OPERATOR_ROOT/tools/run-research-single-cycle.sh"
PROJECT_ID="${1:-}"

if [ -z "$PROJECT_ID" ]; then
  echo "Usage: $0 <project_id>"
  echo "Example: $0 proj-20260225-654f85b2"
  exit 2
fi

if [ ! -d "$OPERATOR_ROOT/research/$PROJECT_ID" ]; then
  echo "Project not found: $PROJECT_ID"
  exit 1
fi

MAX_RUNS=25
# Allow 3 runs in same phase so conductor can do one extra round and we still advance (phase-by-phase stabilization)
# 25: follow-ups with many conductor overrides (explore/focus/connect repeats) need >10 runs to reach done
MAX_SAME_PHASE=3
run=0
last_phase=""
same_phase_count=0

while [ $run -lt $MAX_RUNS ]; do
  phase=$(python3 -c "import json; d=json.load(open('$OPERATOR_ROOT/research/$PROJECT_ID/project.json')); print(d.get('phase',''), end='')")
  status=$(python3 -c "import json; d=json.load(open('$OPERATOR_ROOT/research/$PROJECT_ID/project.json')); print(d.get('status',''), end='')")

  case "$status" in
    done)
      echo "Project $PROJECT_ID is done."
      ls -la "$OPERATOR_ROOT/research/$PROJECT_ID/reports/" 2>/dev/null || true
      exit 0
      ;;
    pending_review)
      echo "Project $PROJECT_ID reached manual review gate: $status (phase: $phase). Stopping."
      exit 0
      ;;
    failed*|cancelled|error|abandoned|aem_blocked)
      echo "Project $PROJECT_ID reached terminal failure status: $status (phase: $phase). Stopping." >&2
      exit 1
      ;;
  esac

  if [ "$phase" = "$last_phase" ]; then
    same_phase_count=$((same_phase_count + 1))
    if [ "$same_phase_count" -ge "$MAX_SAME_PHASE" ]; then
      echo "Phase '$phase' stuck after $same_phase_count retries without advancing. Marking project failed and stopping."
      python3 -c "
import json
from pathlib import Path
p = Path('$OPERATOR_ROOT/research/$PROJECT_ID/project.json')
if p.exists():
    d = json.loads(p.read_text())
    d['status'] = 'failed_stuck_phase'
    p.write_text(json.dumps(d, indent=2))
" 2>/dev/null || true
      python3 -c "
import json
from pathlib import Path
prog = Path('$OPERATOR_ROOT/research/$PROJECT_ID/progress.json')
if prog.exists():
    d = json.loads(prog.read_text())
    d['alive'] = False
    prog.write_text(json.dumps(d, indent=2))
" 2>/dev/null || true
      exit 1
    fi
  else
    same_phase_count=0
  fi
  last_phase="$phase"

  run=$((run + 1))
  echo "[Run $run] Phase: $phase, Status: $status — starting single cycle..."
  run_exit=0
  bash "$RUN_SINGLE_CYCLE" "$PROJECT_ID" || run_exit=$?
  # Exit 2 = skipped (e.g. lock held by another cycle). Do not count toward stuck-phase.
  if [ "$run_exit" -eq 2 ]; then
    echo "[Run $run] Skipped (another cycle running). Not counting toward stuck." >&2
    run=$((run - 1))
    if [ "$same_phase_count" -gt 0 ]; then same_phase_count=$((same_phase_count - 1)); fi
    sleep 2
    continue
  fi
  if [ "$run_exit" -ne 0 ]; then
    echo "[Run $run] Job exited with $run_exit — continuing next run (phase may have advanced)." >&2
  else
    echo "[Run $run] Done."
  fi
done

echo "Stopped after $MAX_RUNS runs without terminal completion. Check project: $OPERATOR_ROOT/research/$PROJECT_ID/project.json" >&2
exit 1
