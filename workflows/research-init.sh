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
proj_dir, question = sys.argv[1], sys.argv[2]
p = Path(proj_dir)
project = {
  "id": p.name,
  "question": question,
  "status": "active",
  "phase": "explore",
  "playbook_id": "general",
  "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  "domain": "general",
  "config": {"max_sources": 50, "max_findings": 200}
}
(p / "project.json").write_text(json.dumps(project, indent=2))
(p / "questions.json").write_text(json.dumps({"open": [question], "answered": []}, indent=2))
(p / "thesis.json").write_text(json.dumps({"current": "", "confidence": 0.0, "evidence": []}, indent=2))
PY

# Seed prior knowledge (utility-ranked principles + findings) for better initial queries
python3 "$OPERATOR_ROOT/tools/research_knowledge_seed.py" "$PROJECT_ID" 2>> "$PWD/log.txt" || true

echo "$PROJECT_ID" > "$ART/project_id.txt"
echo "Created project: $PROJECT_ID" >> "$PWD/log.txt"
echo "$PROJECT_ID"
