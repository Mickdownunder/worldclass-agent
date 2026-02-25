#!/usr/bin/env python3
"""
Fetch a URL and extract main text content for research.
Outputs JSON: { "url", "title", "text", "error", "error_code", "message" }.
Never hard-crash: on dependency/network errors emit structured JSON and exit 0 so caller can count failures.

Usage:
  research_web_reader.py <url>
"""
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Lazy imports to allow preflight to fail first; graceful fallback if called without deps
def _get_bs4():
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup
    except ImportError as e:
        return None

def _get_readability():
    try:
        from readability import Document
        return Document
    except ImportError:
        return None


def fetch_url(url: str, timeout: int = 15) -> bytes:
    req = Request(url, headers={"User-Agent": "OperatorResearch/1.0 (research bot)"})
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def extract_with_readability(html: str, url: str, Document_cls, BeautifulSoup_cls) -> tuple[str, str]:
    doc = Document_cls(html)
    title = doc.title() or ""
    content = doc.summary()
    soup = BeautifulSoup_cls(content, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text[:150000]  # cap size


def extract_with_bs4(html: str, BeautifulSoup_cls) -> tuple[str, str]:
    soup = BeautifulSoup_cls(html, "html.parser")
    for tag in ("script", "style", "nav", "footer", "header"):
        for e in soup.find_all(tag):
            e.decompose()
    title = ""
    t = soup.find("title")
    if t:
        title = t.get_text(strip=True)
    body = soup.find("body") or soup
    text = body.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text[:150000]


def main():
    if len(sys.argv) < 2:
        print("Usage: research_web_reader.py <url>", file=sys.stderr)
        sys.exit(2)
    url = sys.argv[1].strip()
    out = {"url": url, "title": "", "text": "", "error": "", "error_code": "", "message": ""}

    # Dependency check: emit structured error instead of crashing
    BeautifulSoup_cls = _get_bs4()
    if BeautifulSoup_cls is None:
        out["error"] = "No module named 'bs4'"
        out["error_code"] = "dependency_missing"
        out["message"] = "Required module 'bs4' not installed. Install: pip install beautifulsoup4"
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    Document_cls = _get_readability()
    HAS_READABILITY = Document_cls is not None

    # PDF: delegate to PDF reader for same JSON shape
    if url.lower().endswith(".pdf"):
        try:
            import subprocess
            tools_dir = Path(__file__).resolve().parent
            pdf_script = tools_dir / "research_pdf_reader.py"
            if pdf_script.exists():
                r = subprocess.run(
                    [sys.executable, str(pdf_script), url],
                    capture_output=True, text=True, timeout=90,
                )
                if r.returncode == 0:
                    data = json.loads(r.stdout)
                    out["title"] = data.get("title", "")
                    out["text"] = data.get("text", "")
                    out["error"] = data.get("error", "")
                    if data.get("error"):
                        out["error_code"] = data.get("error_code", "pdf_read_failed")
                        out["message"] = (data.get("message") or data.get("error", ""))[:500]
                else:
                    out["error"] = (r.stderr or r.stdout or "PDF read failed").strip()[:500]
                    out["error_code"] = "pdf_read_failed"
                    out["message"] = out["error"]
            else:
                out["error"] = "PDF reader not found"
                out["error_code"] = "dependency_missing"
                out["message"] = out["error"]
        except Exception as e:
            out["error"] = str(e)
            out["error_code"] = "pdf_read_error"
            out["message"] = str(e)[:500]
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    try:
        raw = fetch_url(url)
        html = raw.decode("utf-8", errors="replace")
        if HAS_READABILITY:
            title, text = extract_with_readability(html, url, Document_cls, BeautifulSoup_cls)
        else:
            title, text = extract_with_bs4(html, BeautifulSoup_cls)
        out["title"] = title
        out["text"] = text
    except (URLError, HTTPError, OSError) as e:
        out["error"] = str(e)
        out["error_code"] = "fetch_error"
        out["message"] = str(e)[:500]
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
