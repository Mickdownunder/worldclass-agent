#!/usr/bin/env python3
"""
Fetch a URL and extract main text content for research. Outputs JSON: { "url", "title", "text", "error" }.

Usage:
  research_web_reader.py <url>
"""
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Optional: use readability for better extraction
try:
    from readability import Document
    HAS_READABILITY = True
except ImportError:
    HAS_READABILITY = False

from bs4 import BeautifulSoup


def fetch_url(url: str, timeout: int = 15) -> bytes:
    req = Request(url, headers={"User-Agent": "OperatorResearch/1.0 (research bot)"})
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def extract_with_readability(html: str, url: str) -> tuple[str, str]:
    doc = Document(html)
    title = doc.title() or ""
    content = doc.summary()
    soup = BeautifulSoup(content, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text[:150000]  # cap size


def extract_with_bs4(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
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
    out = {"url": url, "title": "", "text": "", "error": ""}
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
                else:
                    out["error"] = (r.stderr or r.stdout or "PDF read failed").strip()[:500]
            else:
                out["error"] = "PDF reader not found"
        except Exception as e:
            out["error"] = str(e)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    try:
        raw = fetch_url(url)
        html = raw.decode("utf-8", errors="replace")
        if HAS_READABILITY:
            title, text = extract_with_readability(html, url)
        else:
            title, text = extract_with_bs4(html)
        out["title"] = title
        out["text"] = text
    except (URLError, HTTPError, OSError) as e:
        out["error"] = str(e)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
