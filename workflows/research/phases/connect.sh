# Phase: CONNECT — contradictions, entity extraction, hypotheses
# Expects: OPERATOR_ROOT, TOOLS, PROJ_DIR, ART, PROJECT_ID, log
set -euo pipefail

log "Phase: CONNECT — contradictions, entity extraction, hypotheses"
if ! python3 -c "import openai" 2>/dev/null; then
  log "OpenAI missing — connect phase failed (failed_dependency_missing_openai)"
  python3 - "$PROJ_DIR" <<'CONNECT_OPENAI_FAIL'
import sys, os
from pathlib import Path
sys.path.insert(0, os.environ.get("OPERATOR_ROOT", "/root/operator"))
from tools.research_preflight import apply_connect_openai_fail_to_project
apply_connect_openai_fail_to_project(Path(sys.argv[1]))
CONNECT_OPENAI_FAIL
  echo "Connect failed — project status set."
  exit 1
fi
progress_step "Building knowledge graph"
timeout 600 python3 "$TOOLS/research_entity_extract.py" "$PROJECT_ID" >> "$PWD/log.txt" 2>&1 || true
progress_step "Finding cross-references"
timeout 300 python3 "$TOOLS/research_reason.py" "$PROJECT_ID" contradiction_detection > "$PROJ_DIR/contradictions.json" 2>> "$PWD/log.txt" || true
timeout 300 python3 "$TOOLS/research_reason.py" "$PROJECT_ID" hypothesis_formation > "$ART/hypotheses.json" 2>> "$PWD/log.txt" || true
if [ -f "$ART/hypotheses.json" ]; then
  python3 - "$PROJ_DIR" "$ART" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
art = Path(sys.argv[2])
try:
  h = json.loads((art / "hypotheses.json").read_text())
except (json.JSONDecodeError, OSError):
  h = {}
hyps = h.get("hypotheses", [])[:1]
th = json.loads((p / "thesis.json").read_text())
th["current"] = hyps[0].get("statement", "") if hyps else ""
th["confidence"] = hyps[0].get("confidence", 0.5) if hyps else 0.0
th["evidence"] = [x.get("evidence_summary", "") for x in hyps]
(p / "thesis.json").write_text(json.dumps(th, indent=2))
PY
fi
advance_phase "verify"
