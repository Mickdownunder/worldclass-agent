#!/usr/bin/env python3
"""
Web search for research.
Single-query mode:
  research_web_search.py "query" [--max 20]

Batch mode:
  research_web_search.py --queries-file <json> [--max-per-query 5]
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

# Allow importing research_common
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import load_secrets, api_retry


def search_brave(query: str, max_results: int = 20) -> list[dict]:
    api_key = load_secrets().get("BRAVE_API_KEY") or os.environ.get("BRAVE_API_KEY")
    if not api_key:
        return []
    url = f"https://api.search.brave.com/res/v1/web/search?q={quote(query)}&count={min(max_results, 20)}"
    req = Request(url, headers={"Accept": "application/json", "X-Subscription-Token": api_key})
    try:
        @api_retry()
        def _do_request():
            with urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        data = _do_request()
    except Exception as e:
        print(f"WARN: Brave search failed: {e}", file=sys.stderr)
        return []
    results = []
    for w in data.get("web", {}).get("results", [])[:max_results]:
        results.append({
            "title": w.get("title", ""),
            "url": w.get("url", ""),
            "description": w.get("description", ""),
            "source": "brave",
            "published_date": w.get("publishedDate") or w.get("date") or "",
        })
    return results


def search_serper(query: str, max_results: int = 20) -> list[dict]:
    api_key = load_secrets().get("SERPER_API_KEY") or os.environ.get("SERPER_API_KEY")
    if not api_key:
        return []
    url = "https://google.serper.dev/search"
    req = Request(
        url,
        data=json.dumps({"q": query, "num": min(max_results, 100)}).encode(),
        headers={"Content-Type": "application/json", "X-API-KEY": api_key},
        method="POST",
    )
    try:
        @api_retry()
        def _do_request():
            with urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        data = _do_request()
    except Exception as e:
        print(f"WARN: Serper search failed: {e}", file=sys.stderr)
        return []
    results = []
    for w in data.get("organic", [])[:max_results]:
        results.append({
            "title": w.get("title", ""),
            "url": w.get("link", ""),
            "description": w.get("snippet", ""),
            "source": "serper",
            "published_date": w.get("date") or w.get("publishedDate") or "",
        })
    return results


def _search_academic(query: str, max_results: int = 10) -> list[dict]:
    try:
        from tools.research_academic import semantic_scholar, arxiv
    except Exception:
        return []
    per = max(1, max_results // 2)
    out = []
    out.extend(semantic_scholar(query, per))
    out.extend(arxiv(query, max_results - per))
    return out[:max_results]


def _search_medical(query: str, max_results: int = 10) -> list[dict]:
    """PubMed + Semantic Scholar for medical/biomedical queries."""
    try:
        from tools.research_academic import pubmed, semantic_scholar
    except Exception:
        return []
    pm_count = max(1, (max_results * 2) // 3)
    ss_count = max_results - pm_count
    out = []
    out.extend(pubmed(query, pm_count))
    out.extend(semantic_scholar(query, ss_count))
    return out[:max_results]


def _load_queries(path: str) -> list[dict]:
    raw = json.loads(Path(path).read_text())
    if isinstance(raw, dict) and isinstance(raw.get("queries"), list):
        return [q for q in raw.get("queries", []) if isinstance(q, dict)]
    if isinstance(raw, list):
        return [q for q in raw if isinstance(q, dict)]
    return []


def _progress_step(message: str, current: int, total: int) -> None:
    project_id = os.environ.get("RESEARCH_PROJECT_ID", "")
    if not project_id:
        return
    try:
        root = Path(__file__).resolve().parent.parent
        from subprocess import run
        run(
            [sys.executable, str(root / "tools" / "research_progress.py"), "step", project_id, message, str(current), str(total)],
            check=False,
            capture_output=True,
        )
    except Exception:
        pass


def _search_web(query: str, max_results: int, secrets: dict) -> list[dict]:
    if secrets.get("BRAVE_API_KEY"):
        return search_brave(query, max_results)
    if secrets.get("SERPER_API_KEY"):
        return search_serper(query, max_results)
    print("WARN: No BRAVE_API_KEY or SERPER_API_KEY set; returning empty results", file=sys.stderr)
    return []


def main():
    if len(sys.argv) < 2:
        print("Usage: research_web_search.py \"query\" [--max 20] | --queries-file <json> [--max-per-query 5]", file=sys.stderr)
        sys.exit(2)

    secrets = load_secrets()

    if "--queries-file" in sys.argv:
        idx = sys.argv.index("--queries-file") + 1
        if idx >= len(sys.argv):
            sys.exit(2)
        qfile = sys.argv[idx]
        max_per_query = 5
        if "--max-per-query" in sys.argv:
            midx = sys.argv.index("--max-per-query") + 1
            if midx < len(sys.argv):
                max_per_query = max(1, min(20, int(sys.argv[midx])))

        queries = _load_queries(qfile)
        valid_queries = [
            (i, q)
            for i, q in enumerate(queries, start=1)
            if str(q.get("query") or "").strip()
        ]
        total = len(valid_queries)
        max_workers = min(8, max(5, (total + 1) // 2))
        all_results: list[dict] = []
        seen_urls: set[str] = set()

        def run_one(args: tuple) -> tuple[int, str, str, str, str, list[dict]]:
            i, q = args
            query = str(q.get("query") or "").strip()
            qtype = str(q.get("type") or "web").lower()
            topic_id = str(q.get("topic_id") or "")
            perspective = str(q.get("perspective") or "")
            if qtype == "medical":
                results = _search_medical(query, max_per_query)
            elif qtype == "academic":
                results = _search_academic(query, max_per_query)
            else:
                results = _search_web(query, max_per_query, secrets)
            return (i, query, topic_id, perspective, qtype, results)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(run_one, (i, q)): i for i, q in valid_queries}
            for future in as_completed(futures):
                try:
                    i, query, topic_id, perspective, qtype, results = future.result()
                    _progress_step(f"Search {i}/{total}: {query[:80]}", i, total)
                    for r in results:
                        url = (r.get("url") or "").strip()
                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)
                        all_results.append(
                            {
                                **r,
                                "query": query,
                                "topic_id": topic_id,
                                "perspective": perspective,
                                "query_type": qtype,
                            }
                        )
                except Exception as e:
                    print(f"WARN: search failed: {e}", file=sys.stderr)
        print(json.dumps(all_results, indent=2, ensure_ascii=False))
        return

    query = sys.argv[1]
    max_results = 20
    if "--max" in sys.argv:
        idx = sys.argv.index("--max") + 1
        if idx < len(sys.argv):
            max_results = int(sys.argv[idx])
    results = _search_web(query, max_results, secrets)
    project_id = os.environ.get("RESEARCH_PROJECT_ID", "")
    if project_id and results:
        try:
            from tools.research_budget import track_api_call
            api_name = "brave_search" if secrets.get("BRAVE_API_KEY") else "serper_search"
            track_api_call(project_id, api_name, count=1)
        except Exception:
            pass
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
