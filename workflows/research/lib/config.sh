# Research phase config: paths, env, phase, memory strategy.
# Expects: OPERATOR_ROOT set and exported; run from job directory (job.json, PWD/artifacts).
TOOLS="$OPERATOR_ROOT/tools"
RESEARCH="$OPERATOR_ROOT/research"
ART="${ART:-$PWD/artifacts}"
# Use repo venv when present (research reader needs beautifulsoup4)
if [ -x "$OPERATOR_ROOT/.venv/bin/python3" ]; then
  export PATH="$OPERATOR_ROOT/.venv/bin:$PATH"
fi
mkdir -p "$ART"

if [ -f "job.json" ]; then
  REQUEST=$(python3 -c "import json; d=json.load(open('job.json')); print(d.get('request',''), end='')")
fi
PROJECT_ID=$(echo "${REQUEST:-$*}" | awk '{print $1}')
if [ -z "$PROJECT_ID" ] || [ ! -d "$RESEARCH/$PROJECT_ID" ]; then
  echo "Usage: research-phase.sh <project_id> (or run from job dir with job.json request)"
  exit 2
fi

PROJ_DIR="$RESEARCH/$PROJECT_ID"
export RESEARCH_PROJECT_ID="$PROJECT_ID"
CYCLE_LOG="$PROJ_DIR/log.txt"
SECRETS="$OPERATOR_ROOT/conf/secrets.env"
[ -f "$SECRETS" ] && set -a && source "$SECRETS" && set +a
POLICY="$OPERATOR_ROOT/conf/policy.env"
[ -f "$POLICY" ] && set -a && source "$POLICY" && set +a
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"
export RESEARCH_SYNTHESIS_MODEL="${RESEARCH_SYNTHESIS_MODEL:-gemini-3.1-pro-preview}"
export RESEARCH_CRITIQUE_MODEL="${RESEARCH_CRITIQUE_MODEL:-gpt-5.2}"
export RESEARCH_VERIFY_MODEL="${RESEARCH_VERIFY_MODEL:-gemini-3.1-pro-preview}"
export RESEARCH_HYPOTHESIS_MODEL="${RESEARCH_HYPOTHESIS_MODEL:-gemini-3.1-pro-preview}"

export RESEARCH_ENABLE_KNOWLEDGE_SEED="${RESEARCH_ENABLE_KNOWLEDGE_SEED:-1}"
export RESEARCH_ENABLE_QUESTION_GRAPH="${RESEARCH_ENABLE_QUESTION_GRAPH:-1}"
export RESEARCH_ENABLE_ACADEMIC="${RESEARCH_ENABLE_ACADEMIC:-1}"
export RESEARCH_ENABLE_TOKEN_GOVERNOR="${RESEARCH_ENABLE_TOKEN_GOVERNOR:-1}"
export RESEARCH_ENABLE_RELEVANCE_GATE="${RESEARCH_ENABLE_RELEVANCE_GATE:-0}"
export RESEARCH_ENABLE_CONTEXT_MANAGER="${RESEARCH_ENABLE_CONTEXT_MANAGER:-1}"
export RESEARCH_ENABLE_DYNAMIC_OUTLINE="${RESEARCH_ENABLE_DYNAMIC_OUTLINE:-0}"
export RESEARCH_ENABLE_CLAIM_STATE_MACHINE="${RESEARCH_ENABLE_CLAIM_STATE_MACHINE:-0}"
export RESEARCH_ENABLE_CONTRADICTION_LINKING="${RESEARCH_ENABLE_CONTRADICTION_LINKING:-0}"
export RESEARCH_ENABLE_FALSIFICATION_GATE="${RESEARCH_ENABLE_FALSIFICATION_GATE:-0}"

IS_FOLLOWUP=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print('1' if d.get('hypothesis_to_test') else '0')" 2>/dev/null || echo "0")
if [ "$IS_FOLLOWUP" = "1" ]; then
  WORKERS=4
else
  WORKERS=8
fi

unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy 2>/dev/null || true
export NO_PROXY="${NO_PROXY:+$NO_PROXY,}api.openai.com,openai.com,generativelanguage.googleapis.com"
export no_proxy="${no_proxy:+$no_proxy,}api.openai.com,openai.com,generativelanguage.googleapis.com"

PHASE=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('phase','explore'), end='')")
QUESTION=$(python3 -c "import json; d=json.load(open('$PROJ_DIR/project.json')); print(d.get('question',''), end='')")
MEMORY_STRATEGY_FILE="$PROJ_DIR/memory_strategy.json"
RESEARCH_MEMORY_RELEVANCE_THRESHOLD="${RESEARCH_MEMORY_RELEVANCE_THRESHOLD:-0.50}"
RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON="${RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON:-{}}"
RESEARCH_MEMORY_CRITIC_THRESHOLD="${RESEARCH_MEMORY_CRITIC_THRESHOLD:-}"
RESEARCH_MEMORY_REVISE_ROUNDS="${RESEARCH_MEMORY_REVISE_ROUNDS:-2}"
if [ "${RESEARCH_MEMORY_V2_ENABLED:-1}" = "1" ] && [ -f "$MEMORY_STRATEGY_FILE" ]; then
  RESEARCH_MEMORY_RELEVANCE_THRESHOLD=$(python3 -c "
import json
from pathlib import Path
p = Path('$MEMORY_STRATEGY_FILE')
v = 0.50
if p.exists():
  try:
    d = json.loads(p.read_text())
    policy = ((d.get('selected_strategy') or {}).get('policy') or {})
    v = float(policy.get('relevance_threshold', 0.50))
  except Exception:
    pass
print(max(0.50, min(0.65, v)), end='')") || RESEARCH_MEMORY_RELEVANCE_THRESHOLD="0.50"
  RESEARCH_MEMORY_CRITIC_THRESHOLD=$(python3 -c "
import json
from pathlib import Path
p = Path('$MEMORY_STRATEGY_FILE')
v = ''
if p.exists():
  try:
    d = json.loads(p.read_text())
    policy = ((d.get('selected_strategy') or {}).get('policy') or {})
    if policy.get('critic_threshold') is not None:
      v = str(max(0.50, min(0.55, float(policy.get('critic_threshold')))))
  except Exception:
    pass
print(v, end='')") || RESEARCH_MEMORY_CRITIC_THRESHOLD=""
  RESEARCH_MEMORY_REVISE_ROUNDS=$(python3 -c "
import json
from pathlib import Path
p = Path('$MEMORY_STRATEGY_FILE')
v = 2
if p.exists():
  try:
    d = json.loads(p.read_text())
    policy = ((d.get('selected_strategy') or {}).get('policy') or {})
    v = int(policy.get('revise_rounds', 2))
  except Exception:
    pass
print(max(1, min(4, v)), end='')") || RESEARCH_MEMORY_REVISE_ROUNDS="2"
  RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON=$(python3 -c "
import json
from pathlib import Path
p = Path('$MEMORY_STRATEGY_FILE')
out = {}
if p.exists():
  try:
    d = json.loads(p.read_text())
    policy = ((d.get('selected_strategy') or {}).get('policy') or {})
    o = policy.get('domain_rank_overrides') or {}
    if isinstance(o, dict):
      out = o
  except Exception:
    pass
print(json.dumps(out), end='')") || RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON="{}"
fi
export RESEARCH_MEMORY_RELEVANCE_THRESHOLD
export RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON
export RESEARCH_MEMORY_CRITIC_THRESHOLD
export RESEARCH_MEMORY_REVISE_ROUNDS

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$CYCLE_LOG" 2>/dev/null; echo "$*" >&2; }
