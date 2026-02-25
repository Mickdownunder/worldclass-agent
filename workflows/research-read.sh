#!/usr/bin/env bash
# Fetch and extract content from URLs (and optionally PDFs). Request = "project_id [url1] [url2] ..."
# If only project_id given, read from project's sources/*.json (url field) up to N sources.
set -euo pipefail

OPERATOR_ROOT="${OPERATOR_ROOT:-/root/operator}"
TOOLS="$OPERATOR_ROOT/tools"
RESEARCH="$OPERATOR_ROOT/research"
ART="$PWD/artifacts"
mkdir -p "$ART"
MAX_READ=10

if [ -f "job.json" ]; then
  REQUEST=$(python3 -c "import json; d=json.load(open('job.json')); print(d.get('request',''), end='')")
fi
REQUEST="${REQUEST:-$*}"
PROJECT_ID=$(echo "$REQUEST" | awk '{print $1}')
if [ -z "$PROJECT_ID" ] || [ ! -d "$RESEARCH/$PROJECT_ID" ]; then
  echo "Usage: research-read.sh <project_id> [url1 url2 ...]"
  exit 2
fi

PROJ_DIR="$RESEARCH/$PROJECT_ID"
SOURCES="$PROJ_DIR/sources"
FINDINGS="$PROJ_DIR/findings"

# Collect URLs: from request (after first token = project_id) or from sources/*.json
URLS=()
rest="${REQUEST#$PROJECT_ID}"
rest="${rest# }"
for u in $rest; do
  case "$u" in
    http://*|https://*) URLS+=("$u") ;;
  esac
done
if [ ${#URLS[@]} -eq 0 ]; then
  for f in "$SOURCES"/*.json; do
    [ -f "$f" ] || continue
    u=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('url',''), end='')")
    [ -n "$u" ] && URLS+=("$u")
  done
fi

if [ ${#URLS[@]} -eq 0 ]; then
  echo "No URLs to read" >> "$PWD/log.txt"
  echo "done"
  exit 0
fi

count=0
for url in "${URLS[@]:0:$MAX_READ}"; do
  [ -n "$url" ] || continue
  if [[ "$url" == *.pdf ]]; then
    python3 "$TOOLS/research_pdf_reader.py" "$url" > "$ART/read_result.json" 2>> "$PWD/log.txt" || continue
  else
    python3 "$TOOLS/research_web_reader.py" "$url" > "$ART/read_result.json" 2>> "$PWD/log.txt" || continue
  fi
  python3 - "$PROJ_DIR" "$ART" "$url" <<'PY'
import json, sys, hashlib
from pathlib import Path
proj_dir, art, url = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
data = json.loads((art / "read_result.json").read_text())
key = hashlib.sha256(url.encode()).hexdigest()[:12]
(proj_dir / "sources" / f"{key}_content.json").write_text(json.dumps(data, indent=2))
# Append one finding per source for synthesize
findings_dir = proj_dir / "findings"
findings_dir.mkdir(exist_ok=True)
text = (data.get("text") or data.get("abstract") or "")[:8000]
if text:
  fid = hashlib.sha256((url + text[:200]).encode()).hexdigest()[:12]
  (findings_dir / f"{fid}.json").write_text(json.dumps({"url": url, "title": data.get("title",""), "excerpt": text[:2000], "source": "read"}, indent=2))
PY
  count=$((count+1))
done

echo "Read $count sources. Findings in $PROJ_DIR/findings" >> "$PWD/log.txt"
echo "done"
