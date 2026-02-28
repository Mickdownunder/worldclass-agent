#!/usr/bin/env python3
"""
Extract 2-5 key facts per high-quality source (content > 3000 chars) for deeper reports.
Adds findings with source="deep_extract". Run after explore and focus read loops.

Usage:
  research_deep_extract.py <project_id>
"""
import json
import os
import re
import sys
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, llm_call

MIN_CONTENT_LEN = 3000
EXTRACT_MODEL = "gpt-4.1-mini"


def _llm_json(system: str, user: str, project_id: str = "") -> list:
    result = llm_call(EXTRACT_MODEL, system, user, project_id=project_id)
    text = (result.text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text).split("```")[0].strip()
    try:
        out = json.loads(text)
        if isinstance(out, dict) and "facts" in out:
            return out["facts"]
        if isinstance(out, list):
            return out[:5]
    except Exception:
        pass
    return []


def _progress_step(project_id: str, message: str, index: int | None = None, total: int | None = None) -> None:
    try:
        from tools.research_progress import step as progress_step
        progress_step(project_id, message, index, total)
    except Exception:
        pass


def run(project_id: str) -> int:
    proj_path = project_dir(project_id)
    if not proj_path.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    proj = load_project(proj_path)
    question = proj.get("question", "")
    sources_dir = proj_path / "sources"
    findings_dir = proj_path / "findings"
    findings_dir.mkdir(parents=True, exist_ok=True)
    url_to_finding_id: dict[str, str] = {}
    for ef in findings_dir.glob("*.json"):
        try:
            ed = json.loads(ef.read_text())
            u = (ed.get("url") or "").strip()
            fid_val = (ed.get("finding_id") or "").strip()
            if u and fid_val:
                url_to_finding_id[u] = fid_val
        except Exception:
            continue
    content_files = [f for f in sources_dir.glob("*_content.json")]
    q_context = f"\n\nResearch question for context: {question}" if question else ""
    system_tpl = """Extract 2-5 key facts or claims from the text that are RELEVANT to the research question. Return JSON: {{"facts": ["fact one", "fact two", ...]}}.
Each fact should be a single sentence or short paragraph. Be specific (numbers, dates, names). Only extract facts that help answer the research question.{q_context}"""
    work: list[tuple[int, str, str, str, str]] = []
    for f in content_files:
        try:
            d = json.loads(f.read_text())
            text = (d.get("text") or d.get("abstract") or "").strip()
        except Exception:
            continue
        if len(text) < MIN_CONTENT_LEN:
            continue
        base_id = f.stem.replace("_content", "")
        url = ""
        title = ""
        meta = sources_dir / f"{base_id}.json"
        if meta.exists():
            try:
                m = json.loads(meta.read_text())
                url = (m.get("url") or "").strip()
                title = (m.get("title") or "").strip()
            except Exception:
                pass
        existing_relevant = True
        for ef in findings_dir.glob("*.json"):
            try:
                ed = json.loads(ef.read_text())
                if ed.get("url") == url and "relevance_score" in ed:
                    if ed["relevance_score"] < 7:
                        existing_relevant = False
                    break
            except Exception:
                continue
        if not existing_relevant:
            continue
        user = f"TEXT:\n{text[:8000]}\n\nReturn only valid JSON with key 'facts'."
        work.append((len(work), system_tpl, user, url, title))
    if not work:
        return 0
    total_work = len(work)
    results_by_index: dict[int, tuple[str, str, list]] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_item = {
            executor.submit(_llm_json, system, user, project_id): (idx, url, title)
            for idx, system, user, url, title in work
        }
        for future in as_completed(future_to_item):
            idx, url, title = future_to_item[future]
            try:
                facts = future.result()
            except Exception:
                facts = []
            if not isinstance(facts, list):
                facts = []
            results_by_index[idx] = (url, title, facts)
            done += 1
            _progress_step(
                project_id,
                "KI: Extracting key facts from sources",
                done,
                total_work,
            )
    added = 0
    for idx in sorted(results_by_index.keys()):
        url, title, facts = results_by_index[idx]
        for i, fact in enumerate(facts):
            if not isinstance(fact, str) or len(fact.strip()) < 10:
                continue
            fid = hashlib.sha256((url + fact[:200] + str(i)).encode()).hexdigest()[:12]
            out_path = findings_dir / f"{fid}.json"
            if out_path.exists():
                continue
            parent_finding_id = url_to_finding_id.get(url, "")
            out_path.write_text(json.dumps({
                "url": url,
                "title": title,
                "excerpt": fact.strip()[:4000],
                "source": "deep_extract",
                "confidence": 0.55,
                "finding_id": f"f_{fid}",
                "parent_finding_id": parent_finding_id,
            }, indent=2))
            added += 1
    return added


def main():
    if len(sys.argv) < 2:
        print("Usage: research_deep_extract.py <project_id>", file=sys.stderr)
        sys.exit(2)
    try:
        n = run(sys.argv[1])
        print(n)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
