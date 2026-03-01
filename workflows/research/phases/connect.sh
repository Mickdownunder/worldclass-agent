# Phase: CONNECT — contradictions, entity extraction, hypotheses
# Expects: OPERATOR_ROOT, TOOLS, PROJ_DIR, ART, PROJECT_ID, log
set -euo pipefail

log "Phase: CONNECT — contradictions, entity extraction, hypotheses"
# Connect Phase 5: status file at start so failure (e.g. entity_extract) is visible (entity_extract_ok=false)
python3 - "$PROJ_DIR" <<'PYINIT'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
p.joinpath("connect").mkdir(parents=True, exist_ok=True)
p.joinpath("connect", "connect_status.json").write_text(json.dumps({
  "entity_extract_ok": False,
  "contradiction_ok": False,
  "hypothesis_ok": False,
  "thesis_updated": False,
}, indent=2))
PYINIT
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
# Connect Phase 5: entity_extract failure fails the phase (no || true); errors visible in log
progress_step "Building knowledge graph"
timeout 600 python3 "$TOOLS/research_entity_extract.py" "$PROJECT_ID" >> "$PWD/log.txt" 2>&1
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
hyps = h.get("hypotheses", [])
first = hyps[0] if hyps else {}
alternatives = [{"statement": x.get("statement", ""), "confidence": x.get("confidence", 0.5)} for x in hyps[1:5]]
contradiction_summary = ""
if (p / "contradictions.json").exists():
  try:
    data = json.loads((p / "contradictions.json").read_text())
    contras = data.get("contradictions", [])[:1]
    if contras:
      contradiction_summary = contras[0].get("summary", contras[0].get("claim", ""))[:300]
  except Exception:
    pass
if not (p / "thesis.json").exists():
  (p / "thesis.json").write_text(json.dumps({"current": "", "confidence": 0.0, "evidence": []}, indent=2))
th = json.loads((p / "thesis.json").read_text())
th["current"] = first.get("statement", "")
th["confidence"] = first.get("confidence", 0.5) if first else 0.0
th["evidence"] = [first.get("evidence_summary", "")] if first else []
th["alternatives"] = alternatives
if contradiction_summary:
  th["contradiction_summary"] = contradiction_summary
# Phase 6: entity_ids = entity names from graph that appear in thesis current
import re
th["entity_ids"] = []
graph_file = p / "connect" / "entity_graph.json"
if graph_file.exists():
  try:
    g = json.loads(graph_file.read_text())
    current_lower = (th.get("current") or "").lower()
    for e in g.get("entities", [])[:40]:
      name = (e.get("name") or "").strip()
      if len(name) > 2 and name.lower() in current_lower:
        th["entity_ids"].append(name)
    th["entity_ids"] = list(dict.fromkeys(th["entity_ids"]))[:15]
  except Exception:
    pass
(p / "thesis.json").write_text(json.dumps(th, indent=2))
PY
fi
# Connect Phase 5: status for observability (always, before advance)
python3 - "$PROJ_DIR" "$ART" <<'PYSTATUS'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
art = Path(sys.argv[2])
p.joinpath("connect").mkdir(parents=True, exist_ok=True)
p.joinpath("connect", "connect_status.json").write_text(json.dumps({
  "entity_extract_ok": True,
  "contradiction_ok": (p / "contradictions.json").exists(),
  "hypothesis_ok": (art / "hypotheses.json").exists(),
  "thesis_updated": (p / "thesis.json").exists(),
}, indent=2))
PYSTATUS
advance_phase "verify"
