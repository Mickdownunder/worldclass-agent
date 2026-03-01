#!/usr/bin/env python3
"""
Discovery Analysis: KG patterns, entity frequency, cross-domain links, contradictions, gaps.
Runs between verify and synthesize in discovery mode. Writes discovery_analysis.json.
Usage: research_discovery_analysis.py <project_id>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _find_transitive_patterns(mem, project_id: str) -> list[dict]:
    """Find A->B and B->C where no direct A->C exists (novel transitive connections)."""
    try:
        rows = mem._conn.execute(
            """
            SELECT r1.entity_a_id AS a, r1.entity_b_id AS b, r1.relation_type AS rel_ab,
                   r2.entity_b_id AS c, r2.relation_type AS rel_bc,
                   e1.name AS name_a, e2.name AS name_b, e3.name AS name_c
            FROM entity_relations r1
            JOIN entity_relations r2 ON r1.entity_b_id = r2.entity_a_id
            LEFT JOIN entity_relations r3 ON r3.entity_a_id = r1.entity_a_id AND r3.entity_b_id = r2.entity_b_id
            JOIN entities e1 ON e1.id = r1.entity_a_id
            JOIN entities e2 ON e2.id = r1.entity_b_id
            JOIN entities e3 ON e3.id = r2.entity_b_id
            WHERE r1.source_project = ? AND r2.source_project = ? AND r3.id IS NULL
            ORDER BY r1.created_at DESC
            LIMIT 20
            """,
            (project_id, project_id),
        ).fetchall()
        return [
            {
                "entity_a": r["name_a"],
                "entity_b": r["name_b"],
                "entity_c": r["name_c"],
                "relation_ab": r["rel_ab"],
                "relation_bc": r["rel_bc"],
                "hypothesis": f"{r['name_a']} may relate to {r['name_c']} via {r['name_b']}",
            }
            for r in rows
        ]
    except Exception:
        return []


def _entity_frequency(mem, project_id: str) -> dict:
    """Classify entities by mention frequency: rare = emerging, common = established."""
    try:
        rows = mem._conn.execute(
            """
            SELECT e.name, e.type, COUNT(m.id) AS mention_count
            FROM entities e
            JOIN entity_mentions m ON m.entity_id = e.id
            WHERE m.project_id = ?
            GROUP BY e.id
            ORDER BY mention_count
            """,
            (project_id,),
        ).fetchall()
        rare = [r for r in rows if r["mention_count"] <= 2]
        common = [r for r in rows if r["mention_count"] >= 5]
        return {
            "emerging_entities": [
                {"name": r["name"], "type": r["type"], "mentions": r["mention_count"]}
                for r in rare[:15]
            ],
            "established_entities": [
                {"name": r["name"], "type": r["type"], "mentions": r["mention_count"]}
                for r in common[:10]
            ],
        }
    except Exception:
        return {"emerging_entities": [], "established_entities": []}


def _cross_domain_insights(mem, project_id: str) -> list[dict]:
    """Find connections between this project and past projects via cross_links similarity."""
    try:
        rows = mem._conn.execute(
            """
            SELECT cl.similarity,
                   fa.content_preview AS preview_current, fa.project_id AS proj_a,
                   fb.content_preview AS preview_past, fb.project_id AS proj_b
            FROM cross_links cl
            JOIN research_findings fa ON cl.finding_a_id = fa.id
            JOIN research_findings fb ON cl.finding_b_id = fb.id
            WHERE fa.project_id = ? OR fb.project_id = ?
            ORDER BY cl.similarity DESC
            LIMIT 10
            """,
            (project_id, project_id),
        ).fetchall()
        out = []
        for r in rows:
            current_preview = (r["preview_current"] or "")[:200]
            past_preview = (r["preview_past"] or "")[:200]
            past_proj = r["proj_b"] if r["proj_a"] == project_id else r["proj_a"]
            out.append({
                "similarity": r["similarity"],
                "current_finding": current_preview,
                "past_finding": past_preview,
                "past_project": past_proj,
            })
        return out
    except Exception:
        return []


def _contradiction_frontier(proj_path: Path) -> list[dict]:
    """Load contradictions and frame them as research frontier opportunities."""
    path = proj_path / "contradictions.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        contras = data.get("contradictions", [])
        return [
            {
                "topic": c.get("claim") or c.get("topic", ""),
                "sides": c.get("summary") or c.get("description", ""),
                "frontier_signal": "Experts disagree -- this is where new research is needed",
            }
            for c in contras[:10]
        ]
    except Exception:
        return []


def _gap_opportunities(proj_path: Path) -> list[dict]:
    """Convert coverage gaps into discovery opportunities."""
    for fname in ("coverage_round3.json", "coverage_round2.json", "coverage_round1.json"):
        path = proj_path / fname
        if path.exists():
            try:
                data = json.loads(path.read_text())
                topics = data.get("topics", [])
                gaps = [t for t in topics if (t.get("coverage") or 0) < 0.3]
                return [
                    {
                        "topic": g.get("topic", ""),
                        "coverage": g.get("coverage", 0),
                        "opportunity": f"Only {(g.get('coverage') or 0) * 100:.0f}% covered -- high novelty potential",
                    }
                    for g in gaps[:10]
                ]
            except Exception:
                pass
    return []


def _local_entity_graph_signals(proj_path: Path) -> dict:
    """Read connect/entity_graph.json for use when Memory has no/little data. Returns entities + relations summary."""
    path = proj_path / "connect" / "entity_graph.json"
    if not path.exists():
        return {"entities": [], "relations": [], "local_patterns": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        entities = list(data.get("entities") or [])[:30]
        relations = list(data.get("relations") or [])[:25]
        # Build simple "local_patterns" (A->B style) so brief LLM can suggest novel connections
        local_patterns = [
            {"entity_a": r.get("from"), "entity_b": r.get("to"), "relation_type": r.get("relation_type", ""), "hypothesis": f"{r.get('from')} relates to {r.get('to')}"}
            for r in relations
        ]
        return {
            "entities": [e.get("name") or e.get("id") for e in entities if (e.get("name") or e.get("id"))],
            "relations": [{"from": r.get("from"), "to": r.get("to"), "type": r.get("relation_type")} for r in relations],
            "local_patterns": local_patterns,
        }
    except Exception:
        return {"entities": [], "relations": [], "local_patterns": []}


def _synthesize_discovery_brief(
    patterns,
    entities,
    cross_links,
    contradictions,
    gaps,
    question: str,
    project_id: str,
    local_graph: dict | None = None,
) -> dict:
    """LLM call to synthesize raw discovery signals into a structured brief."""
    from tools.research_common import llm_call

    system = """You are a research discovery analyst. Given raw signals (graph patterns,
entity frequencies, cross-domain connections, contradictions, and knowledge gaps),
produce a structured discovery brief.

Return JSON only:
{
  "novel_connections": ["Connection 1: ...", "Connection 2: ..."],
  "emerging_concepts": ["Concept: ... | Why emerging: ..."],
  "research_frontier": ["Frontier area 1: ...", "Frontier area 2: ..."],
  "unexplored_opportunities": ["Opportunity 1: ...", "Opportunity 2: ..."],
  "key_hypothesis": "The single most promising hypothesis from all signals"
}
Be specific. Only include genuinely non-obvious insights. No markdown, only JSON."""

    graph_empty = not patterns and not cross_links
    effective_patterns = list(patterns)[:10]
    if not effective_patterns and local_graph and local_graph.get("local_patterns"):
        effective_patterns = local_graph["local_patterns"][:10]

    hint = ""
    if graph_empty:
        hint = "\nNOTE: No graph/cross-domain data yet. Emphasize contradictions and coverage gaps as discovery opportunities. Still produce novel_connections and key_hypothesis from question, gaps, and contradictions (and local entity graph if provided).\n"

    local_block = ""
    if local_graph and (local_graph.get("entities") or local_graph.get("relations")):
        local_block = f"\nLOCAL ENTITY GRAPH (this project's connect phase):\nEntities: {json.dumps(local_graph.get('entities', [])[:20], ensure_ascii=False)}\nRelations: {json.dumps(local_graph.get('relations', [])[:15], ensure_ascii=False)}\n"

    user = f"""RESEARCH QUESTION: {question}{hint}
GRAPH PATTERNS (transitive connections): {json.dumps(effective_patterns, ensure_ascii=False)}
ENTITY FREQUENCY: {json.dumps(entities, ensure_ascii=False)}
CROSS-DOMAIN LINKS: {json.dumps(cross_links[:5], ensure_ascii=False)}
CONTRADICTIONS: {json.dumps(contradictions[:5], ensure_ascii=False)}
KNOWLEDGE GAPS: {json.dumps(gaps[:5], ensure_ascii=False)}{local_block}
"""
    try:
        result = llm_call("gemini-2.5-flash", system, user, project_id=project_id)
        text = (result.text or "").strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.lower().startswith("json"):
                    text = text[4:].strip()
        return json.loads(text)
    except Exception:
        return {
            "novel_connections": [],
            "emerging_concepts": [],
            "research_frontier": [],
            "unexplored_opportunities": [],
            "key_hypothesis": "",
        }


def run_discovery_analysis(project_id: str) -> dict:
    """Run full discovery analysis. Writes discovery_analysis.json to project dir."""
    from tools.research_common import project_dir, load_project
    from lib.memory import Memory

    proj_path = project_dir(project_id)
    if not proj_path.exists():
        return {}

    mem = Memory()
    try:
        patterns = _find_transitive_patterns(mem, project_id)
        entities = _entity_frequency(mem, project_id)
        cross_links = _cross_domain_insights(mem, project_id)
        contradictions = _contradiction_frontier(proj_path)
        gaps = _gap_opportunities(proj_path)
        local_graph = _local_entity_graph_signals(proj_path)

        project = load_project(proj_path)
        question = (project.get("question") or "")[:500]
        brief = _synthesize_discovery_brief(
            patterns, entities, cross_links, contradictions, gaps, question, project_id, local_graph=local_graph
        )

        result = {
            "raw_signals": {
                "transitive_patterns": patterns,
                "entity_frequency": entities,
                "cross_domain_links": cross_links,
                "contradiction_frontier": contradictions,
                "gap_opportunities": gaps,
                "local_entity_graph": local_graph,
            },
            "discovery_brief": brief,
        }

        out_path = proj_path / "discovery_analysis.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result
    finally:
        mem.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: research_discovery_analysis.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1].strip()
    run_discovery_analysis(project_id)


if __name__ == "__main__":
    main()
