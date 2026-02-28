#!/usr/bin/env python3
"""
Entity and relation extraction for research findings (knowledge graph).
Stores results in Memory (entities, entity_relations, entity_mentions).

Usage:
  research_entity_extract.py <project_id>
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import load_secrets, project_dir, load_project, ensure_project_layout


def _model():
    return os.environ.get("RESEARCH_EXTRACT_MODEL", "gpt-4.1-mini")


def _load_findings(proj_path: Path, max_items: int = 50) -> list[dict]:
    findings = []
    for f in (proj_path / "findings").glob("*.json"):
        try:
            findings.append(json.loads(f.read_text()))
        except Exception:
            pass
    return findings[:max_items]


def _llm_json(system: str, user: str) -> dict | list:
    from openai import OpenAI
    secrets = load_secrets()
    client = OpenAI(api_key=secrets.get("OPENAI_API_KEY"))
    resp = client.responses.create(model=_model(), instructions=system, input=user)
    text = (resp.output_text or "").strip()
    if text.startswith("```"):
        import re
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def extract_entities(text: str) -> list[dict]:
    """LLM-based entity extraction. Returns list of {name, type, properties}."""
    if not (text or "").strip():
        return []
    text = text[:15000]
    system = """You are a research analyst. Extract named entities from the text.
Return JSON: [{"name": "...", "type": "person|org|tech|concept|event", "properties": {"key": "value"}}]
Use short canonical names. type must be one of: person, org, tech, concept, event."""
    user = f"TEXT:\n{text}\n\nExtract entities. Return only valid JSON array."
    try:
        out = _llm_json(system, user)
    except Exception:
        return []
    if not isinstance(out, list):
        return []
    return [x for x in out if isinstance(x, dict) and x.get("name") and x.get("type")]


def extract_relations(entities: list[dict], text: str) -> list[dict]:
    """Extract relations between entities. Returns list of {from, to, relation}."""
    if not entities or not (text or "").strip():
        return []
    names = [e.get("name", "") for e in entities if e.get("name")]
    text = text[:12000]
    system = """You are a research analyst. Given entities and text, extract RELATIONS between them.
Return JSON: [{"from": "entity name", "to": "entity name", "relation": "uses|competes_with|created_by|works_for|part_of|..."}]
Only use entity names from the list. relation should be a short verb phrase."""
    user = f"ENTITIES: {json.dumps(names)}\n\nTEXT:\n{text}\n\nExtract relations. Return only valid JSON array."
    try:
        out = _llm_json(system, user)
    except Exception:
        return []
    if not isinstance(out, list):
        return []
    return [x for x in out if isinstance(x, dict) and x.get("from") and x.get("to") and x.get("relation")]


def run_for_project(project_id: str) -> dict:
    """Load findings, extract entities and relations, store in Memory. Returns stats."""
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        return {"error": f"Project not found: {project_id}"}
    ensure_project_layout(proj_path)
    findings = _load_findings(proj_path)
    if not findings:
        return {"entities": 0, "relations": 0, "mentions": 0}
    try:
        from tools.research_progress import step as progress_step
    except Exception:
        progress_step = lambda _pid, _msg, _idx=None, _tot=None: None
    from lib.memory import Memory
    mem = Memory()
    name_to_id: dict[str, str] = {}
    work = []
    for i, f in enumerate(findings):
        excerpt = (f.get("excerpt") or "")[:8000]
        if not excerpt:
            continue
        work.append((i, f, excerpt))
    if not work:
        mem.close()
        return {"entities": 0, "relations": 0, "mentions": 0}
    total_work = len(work)
    results_by_index: dict[int, tuple[dict, str, list[dict]]] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_item = {
            executor.submit(extract_entities, excerpt): (i, f, excerpt)
            for i, f, excerpt in work
        }
        for future in as_completed(future_to_item):
            i, f, excerpt = future_to_item[future]
            try:
                entities = future.result()
            except Exception:
                entities = []
            results_by_index[i] = (f, excerpt, entities)
            done += 1
            progress_step(
                project_id,
                f"Knowledge graph: entities from finding {done}/{total_work}",
                done,
                total_work,
            )
    all_text = []
    for i in sorted(results_by_index.keys()):
        f, excerpt, entities = results_by_index[i]
        all_text.append(excerpt)
        finding_key = (f.get("url") or "")[:200]
        for e in entities:
            name = (e.get("name") or "").strip()
            etype = (e.get("type") or "concept").lower()
            if etype not in ("person", "org", "tech", "concept", "event"):
                etype = "concept"
            try:
                eid = mem.get_or_create_entity(name, etype, e.get("properties"), project_id)
                name_to_id[name] = eid
                mem.insert_entity_mention(eid, project_id, finding_key, excerpt[:300])
            except Exception:
                pass
    combined = "\n\n".join(all_text)[:20000]
    entities_list = list(name_to_id.keys())
    if entities_list:
        progress_step(project_id, "Knowledge graph: extracting relations between entities")
        rels = extract_relations([{"name": n} for n in entities_list], combined)
        for r in rels:
            a, b = name_to_id.get(r["from"]), name_to_id.get(r["to"])
            if a and b:
                mem.insert_entity_relation(a, b, (r.get("relation") or "related")[:100], project_id, combined[:500])
    count_entities = len(name_to_id)
    count_relations = mem._conn.execute("SELECT COUNT(*) as c FROM entity_relations WHERE source_project = ?", (project_id,)).fetchone()["c"]
    count_mentions = mem._conn.execute("SELECT COUNT(*) as c FROM entity_mentions WHERE project_id = ?", (project_id,)).fetchone()["c"]
    mem.close()
    return {"entities": count_entities, "relations": count_relations, "mentions": count_mentions}


def main():
    if len(sys.argv) < 2:
        print("Usage: research_entity_extract.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    result = run_for_project(project_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
