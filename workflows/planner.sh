#!/usr/bin/env bash
set -euo pipefail

# Dynamic Planner — Uses the cognitive core to decide what to do.
# Instead of a fixed workflow sequence, the brain perceives current state,
# reasons about priorities, and decides which workflows to run.

ART="$PWD/artifacts"
mkdir -p "$ART"

OP="/root/operator/bin/op"
BRAIN="/root/operator/bin/brain"
SECRETS="/root/operator/conf/secrets.env"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$PWD/log.txt"; }

# Load secrets for LLM access
if [ -f "$SECRETS" ]; then
  set -a; source "$SECRETS"; set +a
fi

log "Dynamic planner starting..."

# Phase 1: Brain thinks about what to do
log "Brain: perceiving and thinking..."
PLAN=$($BRAIN think --goal "Analyze current system state and decide which maintenance, improvement, or business workflows to run next. Consider: system health, recent job results, client needs, quality trends, and any failures that need addressing. Prioritize actions that either generate revenue or prevent problems." 2>> "$PWD/log.txt" || echo '{"plan":[],"analysis":"Brain unavailable, running default sequence"}')

echo "$PLAN" > "$ART/brain_plan.json"
log "Brain plan generated"

# Phase 2: Extract planned actions and execute
python3 - "$PLAN" "$ART" "$OP" <<'PY'
import json, sys, subprocess, os

plan_raw = sys.argv[1]
art_dir = sys.argv[2]
op = sys.argv[3]
log_path = os.path.join(os.environ.get("PWD", "."), "log.txt")

def log(msg):
    import datetime
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(log_path, "a") as f:
        f.write(f"[{ts}] {msg}\n")

try:
    plan = json.loads(plan_raw)
except json.JSONDecodeError:
    plan = {"plan": [], "analysis": "Could not parse brain output"}

actions = plan.get("plan", [])
analysis = plan.get("analysis", "no analysis")
confidence = plan.get("confidence", 0.5)

log(f"Plan analysis: {analysis}")
log(f"Plan confidence: {confidence}")
log(f"Planned actions: {len(actions)}")

# Available workflows for validation
import pathlib
available = {f.stem for f in pathlib.Path("/root/operator/workflows").glob("*.sh")}

# Default fallback sequence if brain produced nothing
if not actions:
    actions = [
        {"action": "signals", "reason": "collect system signals", "urgency": "medium"},
        {"action": "knowledge-commit", "reason": "persist knowledge", "urgency": "low"},
        {"action": "goal-progress", "reason": "track goals", "urgency": "low"},
    ]
    log("Using fallback action sequence")

results = []
plan_md = [f"# Dynamic Plan", f"", f"Analysis: {analysis}", f"Confidence: {confidence}", f"", f"## Actions"]

for i, action in enumerate(actions[:7], 1):
    wf = action.get("action", "")
    reason = action.get("reason", "")
    urgency = action.get("urgency", "medium")

    if wf not in available:
        log(f"  [{i}] SKIP {wf} (not a known workflow)")
        plan_md.append(f"- SKIP: {wf} — not available ({reason})")
        continue

    log(f"  [{i}] RUN {wf} ({urgency}): {reason}")
    plan_md.append(f"- [{urgency.upper()}] {wf}: {reason}")

    try:
        job_dir = subprocess.check_output(
            [op, "job", "new", "--workflow", wf, "--request", f"planner: {reason}"],
            text=True
        ).strip()

        result = subprocess.run(
            [op, "run", job_dir, "--timeout", "60"],
            capture_output=True, text=True, timeout=70
        )

        status = result.stdout.strip() or "UNKNOWN"
        results.append({"workflow": wf, "status": status, "job_dir": job_dir})
        log(f"  [{i}] {wf} → {status}")
        plan_md.append(f"  Result: {status}")

    except Exception as e:
        log(f"  [{i}] {wf} → ERROR: {e}")
        results.append({"workflow": wf, "status": "ERROR", "error": str(e)})
        plan_md.append(f"  Result: ERROR — {e}")

# Write artifacts
with open(os.path.join(art_dir, "plan.md"), "w") as f:
    f.write("\n".join(plan_md))

with open(os.path.join(art_dir, "plan_results.json"), "w") as f:
    json.dump({"actions": results, "analysis": analysis}, f, indent=2)

log(f"Planner complete: {len(results)} actions executed")
PY

log "Dynamic planner complete"
