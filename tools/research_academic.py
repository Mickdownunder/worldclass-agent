#!/usr/bin/env python3
"""
Query academic and structured data sources for research.
Sources: Semantic Scholar, arXiv, PubMed, SEC EDGAR (company filings).
Output: JSON array of results to stdout.

Usage:
  research_academic.py semantic_scholar "query" [--max 10]
  research_academic.py arxiv "query" [--max 10]
  research_academic.py pubmed "query" [--max 10]
  research_academic.py sec_edgar <ticker_or_cik> [--max 5]
"""
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import load_secrets


def fetch_json(url: str, headers: dict | None = None, timeout: int = 15) -> dict | list:
    req = Request(url, headers=headers or {"User-Agent": "OperatorResearch/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def semantic_scholar(query: str, max_results: int = 10) -> list[dict]:
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote(query)}&limit={min(max_results, 100)}&fields=title,url,abstract,year,authors,venue"
    try:
        data = fetch_json(url)
    except Exception as e:
        print(f"WARN: Semantic Scholar: {e}", file=sys.stderr)
        return []
    results = []
    for p in data.get("data", [])[:max_results]:
        results.append({
            "title": p.get("title", ""),
            "url": p.get("url", ""),
            "abstract": p.get("abstract", ""),
            "year": p.get("year"),
            "authors": [a.get("name") for a in p.get("authors", [])],
            "venue": p.get("venue", ""),
            "source": "semantic_scholar",
        })
    return results


def arxiv(query: str, max_results: int = 10) -> list[dict]:
    url = f"http://export.arxiv.org/api/query?search_query=all:{quote(query)}&start=0&max_results={min(max_results, 30)}&sortBy=relevance"
    try:
        import xml.etree.ElementTree as ET
        req = Request(url, headers={"User-Agent": "OperatorResearch/1.0"})
        with urlopen(req, timeout=15) as r:
            tree = ET.parse(r)
        root = tree.getroot()
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        results = []
        for entry in root.findall("atom:entry", ns)[:max_results]:
            title = entry.findtext("atom:title", "", ns) or ""
            title = title.replace("\n", " ").strip()
            link = ""
            for e in entry.findall("atom:link", ns):
                if e.get("type") == "text/html":
                    link = e.get("href", "")
                    break
            summary = entry.findtext("atom:summary", "", ns) or ""
            summary = summary.replace("\n", " ").strip()[:2000]
            published = entry.findtext("atom:published", "", ns) or ""
            results.append({
                "title": title,
                "url": link,
                "abstract": summary,
                "published": published[:10] if published else "",
                "source": "arxiv",
            })
        return results
    except Exception as e:
        print(f"WARN: arXiv: {e}", file=sys.stderr)
        return []


def _pubmed_fetch_abstracts(id_list: list[str]) -> dict[str, str]:
    """Fetch abstracts for PubMed IDs via efetch XML API."""
    if not id_list:
        return {}
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    url = f"{base}/efetch.fcgi?db=pubmed&id={','.join(id_list)}&rettype=abstract&retmode=xml"
    abstracts: dict[str, str] = {}
    try:
        import xml.etree.ElementTree as ET
        req = Request(url, headers={"User-Agent": "OperatorResearch/1.0"})
        with urlopen(req, timeout=20) as r:
            tree = ET.parse(r)
        for article in tree.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            if pmid_el is None:
                continue
            pmid = pmid_el.text or ""
            abstract_parts = []
            for text_el in article.findall(".//AbstractText"):
                label = text_el.get("Label", "")
                content = (text_el.text or "").strip()
                if label and content:
                    abstract_parts.append(f"{label}: {content}")
                elif content:
                    abstract_parts.append(content)
            if abstract_parts:
                abstracts[pmid] = " ".join(abstract_parts)[:3000]
    except Exception as e:
        print(f"WARN: PubMed efetch: {e}", file=sys.stderr)
    return abstracts


def pubmed(query: str, max_results: int = 10) -> list[dict]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    try:
        search_url = f"{base}/esearch.fcgi?db=pubmed&term={quote(query)}&retmax={min(max_results, 50)}&retmode=json&sort=relevance"
        search_data = fetch_json(search_url)
        id_list = search_data.get("esearchresult", {}).get("idlist", [])[:max_results]
        if not id_list:
            return []
        summary_url = f"{base}/esummary.fcgi?db=pubmed&id={','.join(id_list)}&retmode=json"
        sum_data = fetch_json(summary_url)
        abstracts = _pubmed_fetch_abstracts(id_list)
        results = []
        for uid in id_list:
            s = sum_data.get("result", {}).get(uid, {})
            authors = s.get("authors", [])
            author_names = [a.get("name", "") if isinstance(a, dict) else str(a) for a in authors]
            results.append({
                "title": s.get("title", ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                "abstract": abstracts.get(uid, ""),
                "description": abstracts.get(uid, "")[:500],
                "published": s.get("pubdate", ""),
                "authors": author_names,
                "source": "pubmed",
                "pmid": uid,
                "source_quality": "peer_reviewed",
            })
        return results
    except Exception as e:
        print(f"WARN: PubMed: {e}", file=sys.stderr)
        return []


def sec_edgar(ticker_or_cik: str, max_results: int = 5) -> list[dict]:
    # SEC company search: ticker or CIK -> company facts / filings
    ticker_or_cik = ticker_or_cik.strip().upper()
    try:
        # Company tickers JSON (SEC)
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker_or_cik}&type=10-K&count={max_results}&output=atom"
        req = Request(url, headers={"User-Agent": "OperatorResearch/1.0 (research)"})
        with urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8", errors="replace")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(raw)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        results = []
        for entry in root.findall("atom:entry", ns)[:max_results]:
            title = entry.findtext("atom:title", "", ns) or ""
            link = ""
            for e in entry.findall("atom:link", ns):
                if "filing" in (e.get("href") or ""):
                    link = e.get("href", "")
                    break
            updated = entry.findtext("atom:updated", "", ns) or ""
            results.append({
                "title": title,
                "url": link,
                "filing_type": "10-K" if "10-K" in title else "filing",
                "updated": updated[:10] if updated else "",
                "source": "sec_edgar",
            })
        return results
    except Exception as e:
        print(f"WARN: SEC EDGAR: {e}", file=sys.stderr)
        return []


def main():
    if len(sys.argv) < 3 and (len(sys.argv) < 2 or sys.argv[1] not in ("semantic_scholar", "arxiv", "pubmed", "sec_edgar")):
        print("Usage: research_academic.py <semantic_scholar|arxiv|pubmed|sec_edgar> <query_or_ticker> [--max N]", file=sys.stderr)
        sys.exit(2)
    source = sys.argv[1].lower()
    query = sys.argv[2] if len(sys.argv) > 2 else ""
    max_results = 10
    if "--max" in sys.argv:
        idx = sys.argv.index("--max") + 1
        if idx < len(sys.argv):
            max_results = int(sys.argv[idx])
    if source == "semantic_scholar":
        results = semantic_scholar(query, max_results)
    elif source == "arxiv":
        results = arxiv(query, max_results)
    elif source == "pubmed":
        results = pubmed(query, max_results)
    elif source == "sec_edgar":
        results = sec_edgar(query or "AAPL", max_results)
    else:
        results = []
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
