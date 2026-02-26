#!/usr/bin/env python3
"""
Web search for research. Uses Brave Search API or Serper.dev (env: BRAVE_API_KEY or SERPER_API_KEY).
Outputs JSON array of results to stdout.

Usage:
  research_web_search.py "query" [--max 20]
"""
import json
import os
import sys
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


def main():
    if len(sys.argv) < 2:
        print("Usage: research_web_search.py \"query\" [--max 20]", file=sys.stderr)
        sys.exit(2)
    query = sys.argv[1]
    max_results = 20
    if "--max" in sys.argv:
        idx = sys.argv.index("--max") + 1
        if idx < len(sys.argv):
            max_results = int(sys.argv[idx])
    secrets = load_secrets()
    if secrets.get("BRAVE_API_KEY"):
        results = search_brave(query, max_results)
    elif secrets.get("SERPER_API_KEY"):
        results = search_serper(query, max_results)
    else:
        print("WARN: No BRAVE_API_KEY or SERPER_API_KEY set; returning empty results", file=sys.stderr)
        results = []
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
