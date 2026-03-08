#!/usr/bin/env bash
# Create a new research project. Request = research question (one line).
# Outputs project_id to artifacts/project_id.txt
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
RESEARCH="$OPERATOR_ROOT/research"
ART="$PWD/artifacts"
mkdir -p "$ART"

# Request = research question. When run as job, read from job.json.
if [ -f "job.json" ]; then
  REQUEST=$(python3 -c "import json; d=json.load(open('job.json')); print(d.get('request',''), end='')")
fi
REQUEST="${REQUEST:-$*}"
if [ -z "$REQUEST" ]; then
  echo "Usage: research-init.sh <research_question> (or set request in job)"
  exit 2
fi

PROJECT_ID="proj-$(date +%Y%m%d)-$(openssl rand -hex 4 2>/dev/null || echo $$)"
PROJ_DIR="$RESEARCH/$PROJECT_ID"
mkdir -p "$PROJ_DIR/findings" "$PROJ_DIR/sources" "$PROJ_DIR/reports"

python3 - "$PROJ_DIR" "$REQUEST" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
proj_dir, request_raw = sys.argv[1], sys.argv[2]
p = Path(proj_dir)
# Request can be JSON {"question": "...", "research_mode": "standard"|"frontier"} or plain question string
question = request_raw.strip()
research_mode = "standard"
hypothesis = ""
parent_project_id = ""
mission_id = ""
control_plane_owner = ""
source_command = ""
if question.startswith("{"):
    try:
        payload = json.loads(question)
        question = (payload.get("question") or "").strip() or question
        research_mode = (payload.get("research_mode") or "standard").strip().lower()
        if research_mode not in ("standard", "frontier", "discovery"):
            research_mode = "standard"
        hypothesis = (payload.get("hypothesis_to_test") or "").strip()
        parent_project_id = (payload.get("parent_project_id") or "").strip()
        mission_id = (payload.get("mission_id") or "").strip()
        control_plane_owner = (payload.get("control_plane_owner") or "").strip()
        source_command = (payload.get("source_command") or "").strip()
    except Exception:
        pass
project = {
  "id": p.name,
  "question": question,
  "status": "active",
  "phase": "explore",
  "playbook_id": "general",
  "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  "domain": "general",
  "config": {"max_sources": 15, "max_findings": 50, "research_mode": research_mode}
}
if hypothesis:
    project["hypothesis_to_test"] = hypothesis
if parent_project_id:
    project["parent_project_id"] = parent_project_id
    parent_project_path = p.parent / parent_project_id / "project.json"
    if parent_project_path.is_file():
        try:
            parent_data = json.loads(parent_project_path.read_text(encoding="utf-8"))
            parent_domain = (parent_data.get("domain") or "").strip()
            if parent_domain:
                project["domain"] = parent_domain
        except Exception:
            pass
if mission_id:
    project["mission_id"] = mission_id
if control_plane_owner:
    project["control_plane_owner"] = control_plane_owner
if source_command:
    project["source_command"] = source_command
(p / "project.json").write_text(json.dumps(project, indent=2))
(p / "questions.json").write_text(json.dumps({"open": [question], "answered": []}, indent=2))
(p / "thesis.json").write_text(json.dumps({"current": "", "confidence": 0.0, "evidence": []}, indent=2))
PY

# Seed prior knowledge (utility-ranked principles + findings) for better initial queries
python3 "$OPERATOR_ROOT/tools/research_knowledge_seed.py" "$PROJECT_ID" 2>> "$PWD/log.txt" || true

echo "$PROJECT_ID" > "$ART/project_id.txt"
echo "Created project: $PROJECT_ID" >> "$PWD/log.txt"
echo "$PROJECT_ID"
