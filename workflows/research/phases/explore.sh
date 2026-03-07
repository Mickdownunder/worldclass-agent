    log "Phase: EXPLORE — 3-round adaptive planning/search/read/coverage"
    progress_start "explore"

    # Core 10: token governor lane for this phase (tools may read RESEARCH_GOVERNOR_LANE or governor_lane.json)
    if [ "${RESEARCH_ENABLE_TOKEN_GOVERNOR:-1}" = "1" ]; then
      GOVERNOR_LANE=$(python3 -c "import sys; sys.path.insert(0,'$OPERATOR_ROOT'); from tools.research_token_governor import recommend_lane; print(recommend_lane('$PROJECT_ID'))" 2>/dev/null || echo "mid")
      export RESEARCH_GOVERNOR_LANE="${GOVERNOR_LANE:-mid}"
      echo "\"$GOVERNOR_LANE\"" > "$PROJ_DIR/governor_lane.json" 2>/dev/null || true
    fi

    # Core 10: prior knowledge and question graph before planner (Welle 1)
    if [ "${RESEARCH_ENABLE_KNOWLEDGE_SEED:-0}" = "1" ]; then
      python3 "$TOOLS/research_knowledge_seed.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    if [ "${RESEARCH_ENABLE_QUESTION_GRAPH:-0}" = "1" ]; then
      python3 "$TOOLS/research_question_graph.py" build "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi

    progress_step "Creating research plan"
    log "Starting: research_planner"
    timeout 300 python3 "$TOOLS/research_planner.py" "$QUESTION" "$PROJECT_ID" > "$ART/research_plan.json" 2>> "$CYCLE_LOG" || true
    if [ ! -s "$ART/research_plan.json" ]; then
      log "Planner failed or timed out — using full fallback plan (question-derived queries)"
      python3 "$TOOLS/research_planner.py" --fallback-only "$QUESTION" "$PROJECT_ID" > "$ART/research_plan.json" 2>> "$CYCLE_LOG" || true
    fi
    if [ ! -s "$ART/research_plan.json" ]; then
      echo '{"queries":[],"topics":[],"complexity":"moderate"}' > "$ART/research_plan.json"
      log "Fallback plan failed — using empty plan (no queries)"
    fi
    log "Done: research_planner"
    cp "$ART/research_plan.json" "$PROJ_DIR/research_plan.json"

    QUERY_COUNT=$(python3 -c "import json; d=json.load(open('$ART/research_plan.json')); print(len(d.get('queries',[])), end='')" 2>/dev/null || echo "0")
    COMPLEXITY=$(python3 -c "import json; d=json.load(open('$ART/research_plan.json')); print(d.get('complexity','moderate'), end='')" 2>/dev/null || echo "moderate")
    if [ "$IS_FOLLOWUP" = "1" ]; then
      READ_LIMIT=10
    else
      READ_LIMIT=$(python3 -c "c='$COMPLEXITY'; print(40 if c=='complex' else 25 if c=='moderate' else 15, end='')")
    fi

    progress_step "Searching $QUERY_COUNT targeted queries"
    python3 "$TOOLS/research_web_search.py" --queries-file "$ART/research_plan.json" --max-per-query 5 > "$ART/web_search_round1.json" 2>> "$CYCLE_LOG" || true

    # Core 10: academic sources into URL pool (Welle 1)
    if [ "${RESEARCH_ENABLE_ACADEMIC:-0}" = "1" ]; then
      mkdir -p "$PROJ_DIR/sources"
      python3 "$TOOLS/research_academic.py" semantic_scholar "$QUESTION" --max 5 > "$ART/academic_round1.json" 2>> "$CYCLE_LOG" || true
      if [ -s "$ART/academic_round1.json" ]; then
        python3 - "$PROJ_DIR" "$ART/academic_round1.json" <<'MERGE_ACADEMIC' 2>> "$CYCLE_LOG" || true
import json, sys, hashlib
from pathlib import Path
proj_dir, path = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(path.read_text()) if path.exists() else []
for item in (data if isinstance(data, list) else []):
    url = (item.get("url") or "").strip()
    if not url: continue
    fid = hashlib.sha256(url.encode()).hexdigest()[:12]
    out = dict(item)
    out.setdefault("title", out.get("abstract", "")[:200])
    out.setdefault("description", out.get("abstract", ""))
    out["confidence"] = 0.5
    out["source_quality"] = "academic"
    (proj_dir / "sources" / f"{fid}.json").write_text(json.dumps(out))
MERGE_ACADEMIC
      fi
    fi

    python3 - "$PROJ_DIR" "$ART/research_plan.json" "$ART/web_search_round1.json" <<'FILTER_AND_SAVE'
import json, sys, hashlib, re
from pathlib import Path
proj_dir = Path(sys.argv[1]); plan_path = Path(sys.argv[2]); search_path = Path(sys.argv[3])
plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}
results = json.loads(search_path.read_text()) if search_path.exists() else []
q_terms = set()
for q in plan.get("queries", []):
    qq = str(q.get("query","")).lower()
    for t in re.findall(r"[a-z0-9\-\+]{3,}", qq):
        q_terms.add(t)
for e in plan.get("entities", []):
    for t in re.findall(r"[a-z0-9\-\+]{3,}", str(e).lower()):
        q_terms.add(t)
topic_ids = {str(t.get("id","")) for t in plan.get("topics", [])}
saved = 0
for item in (results if isinstance(results, list) else []):
    url = (item.get("url") or "").strip()
    if not url:
        continue
    title_desc = f"{item.get('title','')} {item.get('description','')} {item.get('abstract','')}".lower()
    has_topic = str(item.get("topic_id","")) in topic_ids if topic_ids else False
    overlap = sum(1 for w in q_terms if w and w in title_desc)
    if not has_topic and overlap < 2:
        continue
    fid = hashlib.sha256(url.encode()).hexdigest()[:12]
    out = dict(item)
    out["confidence"] = float(out.get("confidence", 0.5))
    out["source_quality"] = out.get("source_quality", "unknown")
    (proj_dir / "sources" / f"{fid}.json").write_text(json.dumps(out))
    saved += 1
print(saved)
FILTER_AND_SAVE

    python3 - "$PROJ_DIR" "$ART/research_plan.json" "$ART" <<'SMART_RANK'
import json, os, sys, re
from pathlib import Path
proj_dir = Path(sys.argv[1]); plan = json.loads(Path(sys.argv[2]).read_text()); art = Path(sys.argv[3])
topics = {str(t.get("id","")): t for t in plan.get("topics", [])}
entities = [str(e).lower() for e in plan.get("entities", [])]
source_type_by_topic = {tid: set((t.get("source_types") or [])) for tid, t in topics.items()}
DOMAIN_RANK = {"arxiv.org":10,"semanticscholar.org":10,"nature.com":10,"science.org":10,"pubmed.ncbi.nlm.nih.gov":12,"ncbi.nlm.nih.gov":11,"nih.gov":11,"thelancet.com":11,"nejm.org":11,"bmj.com":10,"jamanetwork.com":10,"who.int":10,"cochranelibrary.com":10,"clinicaltrials.gov":10,"openai.com":9,"anthropic.com":9,"google.com":8,"reuters.com":8,"nytimes.com":8}
DOMAIN_BLOCKLIST = {"reddit.com","zenml.io","truefoundry.com","medium.com","quora.com"}
try:
    overrides = json.loads(os.environ.get("RESEARCH_MEMORY_DOMAIN_OVERRIDES_JSON", "{}"))
    if isinstance(overrides, dict):
        for k, v in overrides.items():
            DOMAIN_RANK[str(k).replace("www.", "")] = int(v)
except Exception:
    pass
per_domain = {}
ranked = []
for f in (proj_dir / "sources").glob("*.json"):
    if f.name.endswith("_content.json"): continue
    try:
        d = json.loads(f.read_text())
    except Exception:
        continue
    url = (d.get("url") or "").strip()
    if not url: continue
    domain = url.split("/")[2].replace("www.","") if "://" in url else ""
    if domain in DOMAIN_BLOCKLIST: continue
    per_domain.setdefault(domain, 0)
    if per_domain[domain] >= 3:
        continue
    tid = str(d.get("topic_id",""))
    topic = topics.get(tid, {})
    priority = int(topic.get("priority", 3))
    prio_boost = {1: 30, 2: 15, 3: 5}.get(priority, 5)
    stypes = source_type_by_topic.get(tid, set())
    type_boost = 0
    if "paper" in stypes and ("arxiv" in domain or "semanticscholar" in domain or "pubmed" in domain or "ncbi" in domain):
        type_boost += 15
    text = f"{d.get('title','')} {d.get('description','')} {d.get('abstract','')}".lower()
    entity_boost = sum(3 for e in entities if e and e in text)
    domain_boost = DOMAIN_RANK.get(domain, 4)
    score = prio_boost + type_boost + entity_boost + domain_boost
    ranked.append((-score, domain, str(f)))
    per_domain[domain] += 1
ranked.sort()
(art / "read_order_round1.txt").write_text("\n".join(path for _, _, path in ranked))
SMART_RANK
    python3 - "$PROJ_DIR" "$ART" "$OPERATOR_ROOT" "$QUESTION" <<FILTER_READ_URLS 2>> "$CYCLE_LOG" || true
import json, sys
from pathlib import Path
proj_dir, art, op_root, question = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
sys.path.insert(0, str(op_root))
order_file = art / "read_order_round1.txt"
if not order_file.exists():
    sys.exit(0)
paths = [ln.strip() for ln in order_file.read_text().splitlines() if ln.strip()]
try:
    from lib.memory import Memory
    with Memory() as mem:
        skip_urls = mem.get_read_urls_for_question(question or "")
except Exception:
    skip_urls = set()
if not skip_urls:
    sys.exit(0)
filtered = []
for p in paths:
    path = Path(p)
    if not path.exists():
        continue
    try:
        u = (json.loads(path.read_text()).get("url") or "").strip()
        if u and u not in skip_urls:
            filtered.append(p)
    except Exception:
        filtered.append(p)
order_file.write_text("\n".join(filtered))
FILTER_READ_URLS

    log "Starting: parallel_reader explore (limit=$READ_LIMIT workers=$WORKERS)"
    read_attempts=0
    read_successes=0
    READ_STATS=$(python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" explore --input-file "$ART/read_order_round1.txt" --read-limit "$READ_LIMIT" --workers "$WORKERS" 2>> "$CYCLE_LOG" | tail -1)
    if [ -n "$READ_STATS" ]; then
      _add=$(echo "$READ_STATS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('read_attempts',0), d.get('read_successes',0))" 2>/dev/null) || true
      read -r _a _s <<< "${_add:-0 0}"
      read_attempts=$((read_attempts + _a))
      read_successes=$((read_successes + _s))
    fi
    log "Done: parallel_reader explore (attempts=$read_attempts successes=$read_successes)"
    SATURATION_DETECTED=0
    python3 "$TOOLS/research_saturation_check.py" "$PROJ_DIR" 2>> "$CYCLE_LOG" || SATURATION_DETECTED=1

    progress_step "Assessing source coverage"
    python3 "$TOOLS/research_coverage.py" "$PROJECT_ID" > "$ART/coverage_round1.json"
    cp "$ART/coverage_round1.json" "$PROJ_DIR/coverage_round1.json"
    COVERAGE_PASS=$(python3 -c "import json; print(json.load(open('$ART/coverage_round1.json')).get('pass', False), end='')" 2>/dev/null || echo "False")

    if [ "$COVERAGE_PASS" != "True" ]; then
      progress_step "Planner Round 2: precision queries"
      python3 "$TOOLS/research_planner.py" --refinement-queries "$ART/coverage_round1.json" "$PROJECT_ID" > "$ART/refinement_queries.json" 2>> "$CYCLE_LOG" || true
      REFINEMENT_COUNT=$(python3 -c "import json; d=json.load(open('$ART/refinement_queries.json')) if __import__('pathlib').Path('$ART/refinement_queries.json').exists() else {}; print(len(d.get('queries', [])), end='')" 2>/dev/null || echo "0")
      if [ "$REFINEMENT_COUNT" -gt 0 ] && [ "$SATURATION_DETECTED" != "1" ]; then
      python3 "$TOOLS/research_web_search.py" --queries-file "$ART/refinement_queries.json" --max-per-query 5 > "$ART/refinement_search.json" 2>> "$CYCLE_LOG" || true
      python3 - "$PROJ_DIR" "$ART/refinement_search.json" <<'SAVE_REFINEMENT'
import json, sys, hashlib
from pathlib import Path
proj_dir, in_path = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(in_path.read_text()) if in_path.exists() else []
for item in (data if isinstance(data, list) else []):
    u = (item.get("url") or "").strip()
    if not u: continue
    sid = hashlib.sha256(u.encode()).hexdigest()[:12]
    (proj_dir / "sources" / f"{sid}.json").write_text(json.dumps(item))
SAVE_REFINEMENT
      python3 -c "
import json
from pathlib import Path
p = Path('$ART/refinement_search.json')
urls = []
if p.exists():
    data = json.loads(p.read_text())
    for item in (data if isinstance(data, list) else []):
        u = (item.get('url') or '').strip()
        if u and u not in urls:
            urls.append(u)
Path('$ART/refinement_urls_to_read.txt').write_text('\n'.join(urls[:10]))
"
      if [ -s "$ART/refinement_urls_to_read.txt" ]; then
        progress_step "Reading refinement sources"
        REF_STATS=$(python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" explore --input-file "$ART/refinement_urls_to_read.txt" --read-limit 10 --workers "$WORKERS" 2>> "$CYCLE_LOG" | tail -1)
        if [ -n "$REF_STATS" ]; then
          _add=$(echo "$REF_STATS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('read_attempts',0), d.get('read_successes',0))" 2>/dev/null) || true
          read -r _a _s <<< "${_add:-0 0}"
          read_attempts=$((read_attempts + _a))
          read_successes=$((read_successes + _s))
        fi
      fi
    fi

      progress_step "Filling coverage gaps (Round 2)"
      python3 "$TOOLS/research_planner.py" --gap-fill "$ART/coverage_round1.json" "$PROJECT_ID" > "$ART/gap_queries.json"
      python3 "$TOOLS/research_web_search.py" --queries-file "$ART/gap_queries.json" --max-per-query 8 > "$ART/gap_search_round2.json" 2>> "$CYCLE_LOG" || true
      python3 - "$PROJ_DIR" "$ART/gap_search_round2.json" <<'SAVE_GAP'
import json, sys, hashlib
from pathlib import Path
proj_dir, in_path = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(in_path.read_text()) if in_path.exists() else []
for item in (data if isinstance(data, list) else []):
    u = (item.get("url") or "").strip()
    if not u: continue
    sid = hashlib.sha256(u.encode()).hexdigest()[:12]
    (proj_dir / "sources" / f"{sid}.json").write_text(json.dumps(item))
SAVE_GAP
      python3 -c "
import json
from pathlib import Path
p = Path('$ART/gap_search_round2.json')
urls = []
if p.exists():
    data = json.loads(p.read_text())
    for item in (data if isinstance(data, list) else []):
        u = (item.get('url') or '').strip()
        if u and u not in urls:
            urls.append(u)
Path('$ART/gap_urls_to_read.txt').write_text('\n'.join(urls[:10]))
"
      if [ -s "$ART/gap_urls_to_read.txt" ] && [ "$SATURATION_DETECTED" != "1" ]; then
        progress_step "Reading gap-fill sources"
        GAP_STATS=$(python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" explore --input-file "$ART/gap_urls_to_read.txt" --read-limit 10 --workers "$WORKERS" 2>> "$CYCLE_LOG" | tail -1)
        if [ -n "$GAP_STATS" ]; then
          _add=$(echo "$GAP_STATS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('read_attempts',0), d.get('read_successes',0))" 2>/dev/null) || true
          read -r _a _s <<< "${_add:-0 0}"
          read_attempts=$((read_attempts + _a))
          read_successes=$((read_successes + _s))
        fi
      fi
      python3 "$TOOLS/research_coverage.py" "$PROJECT_ID" > "$ART/coverage_round2.json"
      cp "$ART/coverage_round2.json" "$PROJ_DIR/coverage_round2.json"

      THIN_TOPICS=$(python3 -c "import json; d=json.load(open('$ART/coverage_round2.json')) if __import__('pathlib').Path('$ART/coverage_round2.json').exists() else json.load(open('$ART/coverage_round1.json')); print(json.dumps(d.get('thin_priority_topics', [])), end='')" 2>/dev/null || echo "[]")
      if [ "$THIN_TOPICS" != "[]" ]; then
        progress_step "Deep-diving thin topics (Round 3)"
        echo "$THIN_TOPICS" > "$ART/thin_topics.json"
        python3 "$TOOLS/research_planner.py" --perspective-rotate "$ART/thin_topics.json" "$PROJECT_ID" > "$ART/depth_queries.json"
        python3 "$TOOLS/research_web_search.py" --queries-file "$ART/depth_queries.json" --max-per-query 5 > "$ART/depth_search_round3.json" 2>> "$CYCLE_LOG" || true
        python3 - "$PROJ_DIR" "$ART/depth_search_round3.json" <<'SAVE_DEPTH'
import json, sys, hashlib
from pathlib import Path
proj_dir, in_path = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(in_path.read_text()) if in_path.exists() else []
for item in (data if isinstance(data, list) else []):
    u = (item.get("url") or "").strip()
    if not u: continue
    sid = hashlib.sha256(u.encode()).hexdigest()[:12]
    (proj_dir / "sources" / f"{sid}.json").write_text(json.dumps(item))
SAVE_DEPTH
        python3 -c "
import json
from pathlib import Path
p = Path('$ART/depth_search_round3.json')
urls = []
if p.exists():
    data = json.loads(p.read_text())
    for item in (data if isinstance(data, list) else []):
        u = (item.get('url') or '').strip()
        if u and u not in urls:
            urls.append(u)
Path('$ART/depth_urls_to_read.txt').write_text('\n'.join(urls[:8]))
"
        if [ -s "$ART/depth_urls_to_read.txt" ] && [ "$SATURATION_DETECTED" != "1" ]; then
          progress_step "Reading depth sources"
          DEPTH_STATS=$(python3 "$TOOLS/research_parallel_reader.py" "$PROJECT_ID" explore --input-file "$ART/depth_urls_to_read.txt" --read-limit 8 --workers "$WORKERS" 2>> "$CYCLE_LOG" | tail -1)
          if [ -n "$DEPTH_STATS" ]; then
            _add=$(echo "$DEPTH_STATS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('read_attempts',0), d.get('read_successes',0))" 2>/dev/null) || true
            read -r _a _s <<< "${_add:-0 0}"
            read_attempts=$((read_attempts + _a))
            read_successes=$((read_successes + _s))
          fi
        fi
        python3 "$TOOLS/research_coverage.py" "$PROJECT_ID" > "$ART/coverage_round3.json"
        cp "$ART/coverage_round3.json" "$PROJ_DIR/coverage_round3.json"
      fi
    else
      log "Coverage passed after Round 1 — skipping Rounds 2-3"
    fi

    progress_step "Extracting findings"
    log "Starting: research_deep_extract"
    timeout 600 python3 "$TOOLS/research_deep_extract.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    log "Done: research_deep_extract"
    # Persist read stats for evidence gate and UI (research_quality_gate._load_explore_stats)
    read_failures=$((read_attempts - read_successes))
    mkdir -p "$PROJ_DIR/explore"
    python3 -c "
import json
from pathlib import Path
p = Path('$PROJ_DIR/explore/read_stats.json')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({
    'read_attempts': $read_attempts,
    'read_successes': $read_successes,
    'read_failures': $read_failures,
}, indent=2))
"
    # Core 10: post-read relevance gate, context compression, dynamic outline (Welle 1–2)
    if [ "${RESEARCH_ENABLE_RELEVANCE_GATE:-0}" = "1" ]; then
      python3 "$TOOLS/research_relevance_gate.py" batch "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    if [ "${RESEARCH_ENABLE_CONTEXT_MANAGER:-0}" = "1" ]; then
      python3 "$TOOLS/research_context_manager.py" add "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    if [ "${RESEARCH_ENABLE_DYNAMIC_OUTLINE:-0}" = "1" ]; then
      python3 "$TOOLS/research_dynamic_outline.py" "$PROJECT_ID" 2>> "$CYCLE_LOG" || true
    fi
    # Guard: do not advance to focus when explore produced no usable evidence.
    # This prevents "focus with 0 findings/0 reads" after transient DNS/search outages.
    FINDINGS_COUNT=$(python3 -c "from pathlib import Path; print(len(list(Path('$PROJ_DIR/findings').glob('*.json'))), end='')" 2>/dev/null || echo "0")
    READ_CONTENT_COUNT=$(python3 -c "from pathlib import Path; print(len(list(Path('$PROJ_DIR/sources').glob('*_content.json'))), end='')" 2>/dev/null || echo "0")
    SOURCE_META_COUNT=$(python3 -c "from pathlib import Path; print(len([f for f in Path('$PROJ_DIR/sources').glob('*.json') if not f.name.endswith('_content.json')]), end='')" 2>/dev/null || echo "0")
    if [ "${FINDINGS_COUNT:-0}" -le 0 ] && [ "${READ_CONTENT_COUNT:-0}" -le 0 ]; then
      log "Explore produced no usable evidence (findings=$FINDINGS_COUNT, read_contents=$READ_CONTENT_COUNT, source_meta=$SOURCE_META_COUNT) — staying in explore."
      python3 - "$PROJ_DIR" "$read_attempts" "$read_successes" "$SOURCE_META_COUNT" <<'NO_EVIDENCE_GUARD'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
proj_dir, read_attempts, read_successes, source_meta = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
p = proj_dir / "project.json"
d = json.loads(p.read_text())
d["phase"] = "explore"
d["status"] = "active"
d["last_phase_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
meta = d.get("runtime_guard") if isinstance(d.get("runtime_guard"), dict) else {}
meta["explore_no_evidence"] = {
    "at": d["last_phase_at"],
    "read_attempts": read_attempts,
    "read_successes": read_successes,
    "source_meta_count": source_meta,
}
d["runtime_guard"] = meta
p.write_text(json.dumps(d, indent=2))
NO_EVIDENCE_GUARD
      progress_done "explore" "Idle"
      exit 0
    fi
    advance_phase "focus"
