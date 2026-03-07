# Phase FOCUS (sourced from research-phase.sh case focus)
log "Phase: FOCUS — targeted deep-dive from coverage gaps"
    progress_start "focus"
    if [ "${RESEARCH_ENABLE_TOKEN_GOVERNOR:-1}" = "1" ]; then
      GOVERNOR_LANE=$(python3 -c "import sys; sys.path.insert(0,'$OPERATOR_ROOT'); from tools.research_token_governor import recommend_lane; print(recommend_lane('$PROJECT_ID'))" 2>/dev/null || echo "mid")
      export RESEARCH_GOVERNOR_LANE="${GOVERNOR_LANE:-mid}"
      echo "\"$GOVERNOR_LANE\"" > "$PROJ_DIR/governor_lane.json" 2>/dev/null || true
    fi
    progress_step "Analyzing coverage gaps"
    # Coverage is copied to PROJ_DIR by explore; use it when FOCUS runs in a separate job
    COV_FILE="$PROJ_DIR/coverage_round3.json"
    [ -f "$COV_FILE" ] || COV_FILE="$PROJ_DIR/coverage_round2.json"
    [ -f "$COV_FILE" ] || COV_FILE="$PROJ_DIR/coverage_round1.json"
    [ -f "$COV_FILE" ] || COV_FILE="$ART/coverage_round3.json"
    [ -f "$COV_FILE" ] || COV_FILE="$ART/coverage_round2.json"
    [ -f "$COV_FILE" ] || COV_FILE="$ART/coverage_round1.json"
    if [ ! -f "$COV_FILE" ]; then
      log "No coverage file found (explore may have run in another job) — using empty focus queries"
      progress_step "No coverage file — continuing with existing sources only"
      echo '{"queries":[]}' > "$ART/focus_queries.json"
    else
      python3 "$TOOLS/research_planner.py" --gap-fill "$COV_FILE" "$PROJECT_ID" > "$ART/focus_queries.json"
    fi
    # Merge verify/deepening_queries (from Verify loop-back) with gap-fill; deepening first, dedupe by query text
    if [ -f "$PROJ_DIR/verify/deepening_queries.json" ]; then
      python3 - "$PROJ_DIR" "$ART" <<'FOCUS_MERGE'
import json, sys
from pathlib import Path
def norm(q):
    if isinstance(q, str):
        return (q or "").strip()[:200], "deepening", "web", ""
    if isinstance(q, dict):
        return (q.get("query") or "").strip()[:200], q.get("topic_id") or "deepening", q.get("type") or "web", q.get("perspective") or ""
    return "", "deepening", "web", ""
proj_dir, art = Path(sys.argv[1]), Path(sys.argv[2])
deep_path = proj_dir / "verify" / "deepening_queries.json"
gap_path = art / "focus_queries.json"
seen = set()
queries = []
for path in [deep_path, gap_path]:
    if not path.exists():
        continue
    try:
        data = json.loads(path.read_text())
        raw = data.get("queries")
        if not isinstance(raw, list):
            raw = []
        for q in raw:
            qtext, topic_id, qtype, perspective = norm(q)
            if not qtext or qtext.lower() in seen:
                continue
            seen.add(qtext.lower())
            queries.append({"query": qtext, "topic_id": topic_id, "type": qtype, "perspective": perspective})
    except Exception:
        pass
gap_path.write_text(json.dumps({"queries": queries}, indent=2, ensure_ascii=False))
FOCUS_MERGE
      log "Merged verify/deepening_queries into focus_queries"
    fi
    progress_step "Searching for sources (KI)"
    python3 "$TOOLS/research_web_search.py" --queries-file "$ART/focus_queries.json" --max-per-query 8 > "$ART/focus_search.json" 2>> "$CYCLE_LOG" || true
    progress_step "Saving and ranking sources"
    python3 - "$PROJ_DIR" "$ART/focus_search.json" <<'FOCUS_SAVE'
import json, sys, hashlib
from pathlib import Path
proj_dir, src = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(src.read_text()) if src.exists() else []
for item in (data if isinstance(data, list) else []):
    url = (item.get("url") or "").strip()
    if not url:
        continue
    sid = hashlib.sha256(url.encode()).hexdigest()[:12]
    (proj_dir / "sources" / f"{sid}.json").write_text(json.dumps(item))
FOCUS_SAVE

    python3 - "$PROJ_DIR" "$ART/focus_queries.json" "$ART" <<'RANK_FOCUS'
import json, os, sys
from pathlib import Path
proj_dir, qpath, art = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
plan = json.loads(qpath.read_text()) if qpath.exists() else {}
topic_boost = {}
for i, q in enumerate(plan.get("queries", [])):
    tid = str(q.get("topic_id",""))
    if tid not in topic_boost:
        topic_boost[tid] = max(1, 10 - i)
DOMAIN_RANK = {"arxiv.org":10,"semanticscholar.org":10,"nature.com":10,"science.org":10,"pubmed.ncbi.nlm.nih.gov":12,"ncbi.nlm.nih.gov":11,"nih.gov":11,"thelancet.com":11,"nejm.org":11,"bmj.com":10,"jamanetwork.com":10,"who.int":10,"cochranelibrary.com":10,"clinicaltrials.gov":10,"openai.com":9,"anthropic.com":9,"reuters.com":8,"nytimes.com":8}
DOMAIN_BLOCKLIST = {"reddit.com","zenml.io","truefoundry.com","medium.com","quora.com"}
try:
    overrides = json.loads(os.environ.get("RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON", "{}"))
    if isinstance(overrides, dict):
        for k, v in overrides.items():
            DOMAIN_RANK[str(k).replace("www.", "")] = int(v)
except Exception:
    pass
ranked = []
for f in (proj_dir / "sources").glob("*.json"):
    if f.name.endswith("_content.json"): continue
    sid = f.stem
    if (proj_dir / "sources" / f"{sid}_content.json").exists(): continue
    try:
        d = json.loads(f.read_text())
    except Exception:
        continue
    url = (d.get("url") or "").strip()
    if not url: continue
    domain = url.split("/")[2].replace("www.","") if "://" in url else ""
    if domain in DOMAIN_BLOCKLIST: continue
    score = DOMAIN_RANK.get(domain, 4) + topic_boost.get(str(d.get("topic_id","")), 0)
    ranked.append((-score, str(f)))
ranked.sort()
(art / "focus_read_order.txt").write_text("\n".join(path for _, path in ranked))
RANK_FOCUS
    FOCUS_STATS=$(python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" focus --input-file "$ART/focus_read_order.txt" --read-limit 15 --workers "$WORKERS" 2>> "$CYCLE_LOG" | tail -1)
    focus_read_attempts=0
    focus_read_successes=0
    focus_read_failures=0
    [ -n "$FOCUS_STATS" ] && read -r focus_read_attempts focus_read_successes focus_read_failures <<< "$(echo "$FOCUS_STATS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('read_attempts',0), d.get('read_successes',0), d.get('read_failures',0))" 2>/dev/null)" 2>/dev/null || true
    [ -z "$focus_read_failures" ] && focus_read_failures=$(( focus_read_attempts - focus_read_successes ))
    mkdir -p "$PROJ_DIR/focus"
    echo "{\"read_attempts\": $focus_read_attempts, \"read_successes\": $focus_read_successes, \"read_failures\": $focus_read_failures}" > "$PROJ_DIR/focus/read_stats.json"
    log "Focus reads: $focus_read_attempts attempted, $focus_read_successes succeeded"
    progress_step "Extracting focused findings"
    timeout 600 python3 "$TOOLS/research_deep_extract.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    if [ "${RESEARCH_ENABLE_CONTEXT_MANAGER:-0}" = "1" ]; then
      python3 "$TOOLS/research_context_manager.py" add "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    # Guard: do not advance to connect when focus produced no usable evidence.
    FOCUS_FINDINGS_COUNT=$(python3 -c "from pathlib import Path; print(len(list(Path('$PROJ_DIR/findings').glob('*.json'))), end='')" 2>/dev/null || echo "0")
    FOCUS_READ_CONTENT_COUNT=$(python3 -c "from pathlib import Path; print(len(list(Path('$PROJ_DIR/sources').glob('*_content.json'))), end='')" 2>/dev/null || echo "0")
    if [ "${FOCUS_FINDINGS_COUNT:-0}" -le 0 ] && [ "${FOCUS_READ_CONTENT_COUNT:-0}" -le 0 ]; then
      log "Focus produced no usable evidence (focus_reads=$focus_read_successes, findings=$FOCUS_FINDINGS_COUNT, read_contents=$FOCUS_READ_CONTENT_COUNT) — staying in focus."
      python3 - "$PROJ_DIR" "$focus_read_attempts" "$focus_read_successes" <<'FOCUS_NO_EVIDENCE_GUARD'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
proj_dir, read_attempts, read_successes = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
p = proj_dir / "project.json"
d = json.loads(p.read_text())
d["phase"] = "focus"
d["status"] = "active"
d["last_phase_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
meta = d.get("runtime_guard") if isinstance(d.get("runtime_guard"), dict) else {}
meta["focus_no_evidence"] = {
    "at": d["last_phase_at"],
    "read_attempts": read_attempts,
    "read_successes": read_successes,
}
d["runtime_guard"] = meta
p.write_text(json.dumps(d, indent=2))
FOCUS_NO_EVIDENCE_GUARD
      progress_done "focus" "Idle"
      exit 0
    fi
    progress_done "focus" "Idle"
    advance_phase "connect"
    # Same-run advance: run connect phase immediately so UI does not stay on "focus" until next cycle
    progress_start "connect"
    source "$OPERATOR_ROOT/workflows/research/phases/connect.sh"
