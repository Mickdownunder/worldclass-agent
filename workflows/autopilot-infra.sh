#!/usr/bin/env bash
set -euo pipefail

# Autopilot — Cognitive cycle for autonomous system operation.
# Uses the brain for intelligent decision-making instead of fixed sequences.

ART="$PWD/artifacts"
mkdir -p "$ART"

OP="/root/operator/bin/op"
BRAIN="/root/operator/bin/brain"
SECRETS="/root/operator/conf/secrets.env"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$PWD/log.txt"; echo "$*" >&2; }

if [ -f "$SECRETS" ]; then
  set -a; source "$SECRETS"; set +a
fi

# Phase 1: Collect signals (always runs, no LLM needed)
log "Phase 1: Collecting signals..."

DISK=$(df / | tail -1 | awk '{print $5}')
LOAD=$(uptime | awk -F'load average:' '{print $2}' | xargs)
PROCS=$(ps aux --sort=-%cpu | head -6)

cat > "$ART/signals.json" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "disk_root_use": "$DISK",
  "load": "$LOAD",
  "top_processes": "$(echo "$PROCS" | tail -5 | awk '{print $11}' | tr '\n' ', ')"
}
EOF

# Phase 2: Brain-powered cognitive cycle
log "Phase 2: Running cognitive cycle..."
CYCLE_RESULT=$($BRAIN cycle --goal "Autonomous maintenance cycle: check system health, run priority maintenance tasks, and ensure client delivery pipeline is healthy. If there are recent failures, prioritize addressing them. If quality is declining, investigate." --governance 2 2>> "$PWD/log.txt" || echo '{"error":"brain unavailable"}')

echo "$CYCLE_RESULT" > "$ART/cycle_result.json"
log "Cognitive cycle result: $(echo "$CYCLE_RESULT" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f"decision={d.get(\"decision\",\"?\")}, quality={d.get(\"quality\",\"?\")}, status={d.get(\"status\",\"?\")}") ' 2>/dev/null || echo "parse error")"

# Phase 3: Knowledge commit
log "Phase 3: Committing knowledge..."
$OP job new --workflow knowledge-commit --request "autopilot memory commit" \
  | xargs -I{} $OP run {} >> "$PWD/log.txt" 2>&1 || true

# Phase 4: Check triggers
PCT=${DISK%\%}
if [ "$PCT" -ge 80 ]; then
  log "TRIGGER: High disk usage ($DISK)"
  echo "TRIGGER: disk >= 80% ($DISK)" >> "$ART/signals.json"
  $OP job new --workflow infra-status --request "autopilot: disk high ($DISK)" \
    | xargs -I{} $OP run {} >> "$PWD/log.txt" 2>&1 || true
fi

# Phase 5: Generate summary
cat > "$ART/proposal.md" <<EOF
# Autopilot Report — $(date -u +%Y-%m-%d)

## Signals
- Disk: $DISK
- Load: $LOAD

## Cognitive Cycle
$(echo "$CYCLE_RESULT" | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    print(f"- Decision: {d.get(\"decision\",\"none\")}")
    print(f"- Status: {d.get(\"status\",\"unknown\")}")
    print(f"- Quality: {d.get(\"quality\",0):.2f}")
    print(f"- Learnings: {d.get(\"learnings\",\"none\")}")
except:
    print("- Error parsing cycle result")
' 2>/dev/null)

## Policy
- JOB_POLICY=${JOB_POLICY:-READ_ONLY}
EOF

log "Autopilot complete"
