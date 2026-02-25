#!/usr/bin/env bash
# Run web + academic search for a research project. Request = project_id (e.g. proj-20260225-abc1).
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
TOOLS="$OPERATOR_ROOT/tools"
RESEARCH="$OPERATOR_ROOT/research"
ART="$PWD/artifacts"
mkdir -p "$ART"

if [ -f "job.json" ]; then
  REQUEST=$(python3 -c "import json; d=json.load(open('job.json')); print(d.get('request',''), end='')")
fi
REQUEST="${REQUEST:-$*}"
PROJECT_ID=$(echo "$REQUEST" | awk '{print $1}')
if [ -z "$PROJECT_ID" ] || [ ! -d "$RESEARCH/$PROJECT_ID" ]; then
  echo "Usage: research-search.sh <project_id> (e.g. proj-20260225-abc1)"
  exit 2
fi

PROJ_DIR="$RESEARCH/$PROJECT_ID"
SECRETS="$OPERATOR_ROOT/conf/secrets.env"
[ -f "$SECRETS" ] && set -a && source "$SECRETS" && set +a

# Get research question from project
QUESTION=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('question',''), end='')")
# Web search (if API key set)
echo "Searching web for: $QUESTION" >> "$PWD/log.txt"
WEB_RESULTS="$ART/web_search.json"
python3 "$TOOLS/research_web_search.py" "$QUESTION" --max 15 > "$WEB_RESULTS" 2>> "$PWD/log.txt" || true
# Academic: Semantic Scholar + arXiv
echo "Searching Semantic Scholar..." >> "$PWD/log.txt"
python3 "$TOOLS/research_academic.py" semantic_scholar "$QUESTION" --max 5 > "$ART/semantic_scholar.json" 2>> "$PWD/log.txt" || true
echo "Searching arXiv..." >> "$PWD/log.txt"
python3 "$TOOLS/research_academic.py" arxiv "$QUESTION" --max 5 > "$ART/arxiv.json" 2>> "$PWD/log.txt" || true

# Merge results into project sources (append new URLs)
python3 - "$PROJ_DIR" "$ART" <<'PY'
import json, sys, hashlib
from pathlib import Path
proj_dir, art = Path(sys.argv[1]), Path(sys.argv[2])
sources_dir = proj_dir / "sources"
sources_dir.mkdir(exist_ok=True)
seen = set()
for name in ["web_search.json", "semantic_scholar.json", "arxiv.json"]:
  p = art / name
  if not p.exists():
    continue
  try:
    data = json.loads(p.read_text())
  except Exception:
    continue
  for item in data if isinstance(data, list) else []:
    url = (item.get("url") or "").strip()
    if not url or url in seen:
      continue
    seen.add(url)
    fid = hashlib.sha256(url.encode()).hexdigest()[:12]
    (sources_dir / f"{fid}.json").write_text(json.dumps(item, indent=2))
PY

echo "Search complete. Sources in $PROJ_DIR/sources" >> "$PWD/log.txt"
echo "done"
