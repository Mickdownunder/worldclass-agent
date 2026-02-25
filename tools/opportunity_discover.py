#!/usr/bin/env python3
"""
Discover real business opportunities from external sources and score them
against client topics using LLM. Writes structured JSONL to stdout.

Sources:
  - HackerNews (top + new stories)
  - Google News RSS (per-topic)

Usage:
  opportunity_discover.py <clients_dir> [--max-items 30]
"""

import json, sys, os, hashlib, time, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from xml.etree import ElementTree


def utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_id(text: str) -> str:
    return "opp_" + hashlib.sha256(text.encode()).hexdigest()[:12]


def fetch_json(url: str, timeout: int = 15) -> dict | list | None:
    try:
        req = Request(url, headers={"User-Agent": "OperatorBot/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (URLError, json.JSONDecodeError, OSError) as e:
        print(f"WARN: fetch {url}: {e}", file=sys.stderr)
        return None


def fetch_text(url: str, timeout: int = 15) -> str | None:
    try:
        req = Request(url, headers={"User-Agent": "OperatorBot/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, OSError) as e:
        print(f"WARN: fetch {url}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Source: HackerNews
# ---------------------------------------------------------------------------

def fetch_hn_stories(story_type: str = "top", limit: int = 30) -> list[dict]:
    """Fetch top/new/best stories from HN API."""
    url = f"https://hacker-news.firebaseio.com/v0/{story_type}stories.json"
    ids = fetch_json(url)
    if not ids:
        return []

    stories = []
    for sid in ids[:limit]:
        item = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
        if not item or item.get("type") != "story":
            continue
        stories.append({
            "title": item.get("title", ""),
            "url": item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
            "score": item.get("score", 0),
            "comments": item.get("descendants", 0),
            "by": item.get("by", ""),
            "source": "hackernews",
        })

    return stories


# ---------------------------------------------------------------------------
# Source: Google News RSS
# ---------------------------------------------------------------------------

def fetch_google_news(query: str, limit: int = 10) -> list[dict]:
    """Fetch Google News RSS for a query."""
    from urllib.parse import quote
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en&gl=US&ceid=US:en"
    xml_text = fetch_text(url)
    if not xml_text:
        return []

    results = []
    try:
        root = ElementTree.fromstring(xml_text)
        for item in root.findall(".//item")[:limit]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            results.append({
                "title": title,
                "url": link,
                "pub_date": pub_date,
                "source": "google_news",
            })
    except ElementTree.ParseError as e:
        print(f"WARN: parse google news: {e}", file=sys.stderr)

    return results


# ---------------------------------------------------------------------------
# LLM Scoring
# ---------------------------------------------------------------------------

def score_opportunities_llm(raw_items: list[dict], all_topics: list[str]) -> list[dict]:
    """Use OpenAI to score and categorize raw items against topics."""
    from openai import OpenAI

    if not raw_items:
        return []

    items_text = json.dumps(raw_items[:40], indent=2, ensure_ascii=False)
    topics_text = ", ".join(sorted(set(all_topics)))

    prompt = f"""You are a business intelligence analyst. Score these items as business opportunities.

TOPICS OF INTEREST: {topics_text}

For each item, determine:
1. relevance_score (0.0-1.0): How relevant is this to the topics?
2. topics: Which topics does it match? (from the list above only)
3. summary: A 1-2 sentence business-relevant summary
4. opportunity_type: One of "trend", "competitor_move", "market_signal", "pain_point", "new_tool", "funding", "other"

Only include items with relevance_score >= 0.4.

Return ONLY a JSON array (no markdown):
[{{"title":"...","summary":"...","score":0.7,"topics":["growth"],"opportunity_type":"trend","evidence":["url"]}}]

ITEMS:
{items_text}"""

    client = OpenAI()
    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )

    text = resp.output_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        scored = json.loads(text)
        if not isinstance(scored, list):
            return []
        return scored
    except json.JSONDecodeError as e:
        print(f"WARN: LLM JSON parse error: {e}", file=sys.stderr)
        print(f"WARN: Raw response: {text[:500]}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def collect_client_topics(clients_dir: Path) -> list[str]:
    """Gather all unique topics from all client configs."""
    topics = set()
    for f in clients_dir.glob("*.json"):
        try:
            c = json.loads(f.read_text())
            for t in c.get("topics", []):
                topics.add(t.lower())
        except (json.JSONDecodeError, OSError):
            pass
    return sorted(topics)


def main():
    if len(sys.argv) < 2:
        print("usage: opportunity_discover.py <clients_dir> [--max-items N]", file=sys.stderr)
        return 2

    clients_dir = Path(sys.argv[1])
    if not clients_dir.is_dir():
        print(f"ERROR: not a directory: {clients_dir}", file=sys.stderr)
        return 1

    max_items = 30
    if "--max-items" in sys.argv:
        max_items = int(sys.argv[sys.argv.index("--max-items") + 1])

    all_topics = collect_client_topics(clients_dir)
    if not all_topics:
        print("ERROR: no topics found in client configs", file=sys.stderr)
        return 1

    print(f"Topics: {all_topics}", file=sys.stderr)

    # 1. Gather raw items from sources
    raw_items = []

    print("Fetching HackerNews top stories...", file=sys.stderr)
    for story in fetch_hn_stories("top", limit=30):
        raw_items.append(story)

    print("Fetching HackerNews new stories...", file=sys.stderr)
    for story in fetch_hn_stories("new", limit=20):
        raw_items.append(story)

    for topic in all_topics[:5]:
        print(f"Fetching Google News for '{topic}'...", file=sys.stderr)
        for item in fetch_google_news(f"{topic} SaaS", limit=5):
            raw_items.append(item)

    print(f"Raw items collected: {len(raw_items)}", file=sys.stderr)

    if not raw_items:
        print("WARN: no raw items collected", file=sys.stderr)
        return 3

    # 2. Score with LLM
    print("Scoring with LLM...", file=sys.stderr)
    scored = score_opportunities_llm(raw_items, all_topics)
    print(f"Scored opportunities: {len(scored)}", file=sys.stderr)

    # 3. Output as JSONL
    now = utcnow_iso()
    count = 0
    seen_titles = set()

    for opp in scored[:max_items]:
        title = opp.get("title", "").strip()
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        record = {
            "id": sha_id(title + now),
            "title": title,
            "summary": opp.get("summary", ""),
            "topics": opp.get("topics", []),
            "score": round(float(opp.get("score", 0.5)), 3),
            "opportunity_type": opp.get("opportunity_type", "other"),
            "evidence": opp.get("evidence", [])[:5],
            "source": "auto_discover",
            "created_at": now,
        }
        print(json.dumps(record, ensure_ascii=False))
        count += 1

    print(f"Output: {count} opportunities", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
