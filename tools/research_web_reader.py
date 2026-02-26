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
from urllib.request import Request, urlopen, ProxyHandler, build_opener
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_PAYWALL_PATTERNS = re.compile(
    r"paywall|subscribe to continue|cookie-consent|access denied|please enable javascript|sign.?in to read|create.?an? account|free trial",
    re.IGNORECASE,
)

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

_JINA_FIRST_DOMAINS = frozenset({
    "theverge.com", "nytimes.com", "wsj.com", "ft.com",
    "bloomberg.com", "arstechnica.com", "fortune.com",
    "washingtonpost.com", "economist.com", "businessinsider.com",
})


def _extract_domain(url: str) -> str:
    try:
        parts = url.split("/")
        return parts[2].replace("www.", "") if len(parts) > 2 else ""
    except Exception:
        return ""


def _detect_paywall(html: str) -> bool:
    """Return True if HTML looks paywalled or bot-blocked (thin body or known patterns)."""
    from html.parser import HTMLParser

    class _BodyExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self._in_body = False
            self.text_parts: list[str] = []
        def handle_starttag(self, tag, attrs):
            if tag == "body":
                self._in_body = True
        def handle_endtag(self, tag):
            if tag == "body":
                self._in_body = False
        def handle_data(self, data):
            if self._in_body:
                self.text_parts.append(data)

    ext = _BodyExtractor()
    try:
        ext.feed(html)
    except Exception:
        pass
    body_text = "".join(ext.text_parts).strip()
    if len(body_text) < 200:
        return True
    if _PAYWALL_PATTERNS.search(html):
        return True
    return False


_COOKIE_CONSENT_PATTERNS = re.compile(
    r"Bevor Sie zu Google weitergehen|"
    r"Before you continue to Google|"
    r"Alle akzeptieren|Accept all|"
    r"cookie-consent-content|"
    r"consent\.google\.com",
    re.IGNORECASE,
)


def _is_cookie_consent(text: str) -> bool:
    """Detect Google/generic cookie consent pages that contain no real article content."""
    if not text or len(text.strip()) < 50:
        return True
    return bool(_COOKIE_CONSENT_PATTERNS.search(text[:2000]))


def fetch_via_google_cache(url: str, timeout: int = 15) -> tuple[str, str]:
    """Try Google's cache of the URL. Returns (title, text)."""
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}&hl=en&gl=us"
    req = Request(cache_url, headers={
        "User-Agent": _BROWSER_UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": "CONSENT=YES+cb.20210720-07-p0.en+FX+111",
    })
    try:
        with urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", errors="replace")
        BeautifulSoup_cls = _get_bs4()
        if BeautifulSoup_cls:
            title, text = extract_with_bs4(html, BeautifulSoup_cls)
            if _is_cookie_consent(text):
                print(f"[google_cache] Cookie-consent page detected for {url}", file=sys.stderr)
                return ("", "")
            return (title, text)
    except Exception:
        pass
    return ("", "")


def fetch_via_jina(url: str, timeout: int = 45) -> tuple[str, str]:
    """Fetch readable content via Jina Reader API using curl subprocess.
    curl has network privileges that Python urlopen lacks in sandboxed environments."""
    import subprocess
    try:
        from tools.research_common import load_secrets
        secrets = load_secrets()
    except Exception:
        secrets = {}
    jina_url = f"https://r.jina.ai/{url}"
    cmd = [
        "curl", "-s", "-S",
        "-H", "Accept: text/markdown",
        "-H", "X-No-Cache: true",
        "-H", f"X-Timeout: {timeout - 10}",
        "--max-time", str(timeout),
    ]
    jina_key = secrets.get("JINA_API_KEY", "")
    if jina_key:
        cmd += ["-H", f"Authorization: Bearer {jina_key}"]
    cmd.append(jina_url)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        if result.returncode != 0:
            err = (result.stderr or "").strip()[:200]
            print(f"[jina] curl error {url}: code={result.returncode} {err}", file=sys.stderr)
            return ("", "")
        md = result.stdout
    except subprocess.TimeoutExpired:
        print(f"[jina] timeout {url} ({timeout}s)", file=sys.stderr)
        return ("", "")
    except Exception as exc:
        print(f"[jina] FAIL {url}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return ("", "")
    if not md or len(md.strip()) < 50:
        return ("", "")
    title = ""
    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            break
    return (title, md[:150000])


def fetch_via_archive(url: str, timeout: int = 20) -> tuple[str, str]:
    """Try Wayback Machine's latest snapshot. Returns (title, text) via Jina on snapshot URL."""
    api_url = f"https://archive.org/wayback/available?url={url}"
    req = Request(api_url, headers={"User-Agent": "OperatorResearch/1.0"})
    try:
        with urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        snapshot_url = data.get("archived_snapshots", {}).get("closest", {}).get("url", "")
        if not snapshot_url:
            return ("", "")
        return fetch_via_jina(snapshot_url, timeout)
    except Exception:
        return ("", "")


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
    req = Request(url, headers={
        "User-Agent": _BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    })
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
    domain = _extract_domain(url)
    jina_first = domain in _JINA_FIRST_DOMAINS
    fallback_chain: list[dict] = []

    if jina_first:
        fb_title, fb_text = fetch_via_jina(url)
        if fb_text.strip() and not _is_cookie_consent(fb_text):
            out["title"] = fb_title
            out["text"] = fb_text
            out["fallback"] = "jina_first"
            fallback_chain.append({"method": "jina_first", "result": "ok"})
        else:
            fallback_chain.append({"method": "jina_first", "result": "empty"})

    if not out["text"]:
        try:
            raw = fetch_url(url)
            html = raw.decode("utf-8", errors="replace")
            if HAS_READABILITY:
                title, text = extract_with_readability(html, url, Document_cls, BeautifulSoup_cls)
            else:
                title, text = extract_with_bs4(html, BeautifulSoup_cls)
            if _detect_paywall(html) or len(text.strip()) < 100 or _is_cookie_consent(text):
                fallback_chain.append({"method": "direct", "result": "paywall_or_thin"})
            else:
                out["title"] = title
                out["text"] = text
                fallback_chain.append({"method": "direct", "result": "ok"})
        except HTTPError as e:
            code = getattr(e, "code", 0)
            fallback_chain.append({"method": "direct", "result": f"http_{code}"})
            if code not in (403, 451):
                out["error"] = str(e)
                out["error_code"] = "fetch_error"
                out["message"] = str(e)[:500]
        except (URLError, OSError) as e:
            fallback_chain.append({"method": "direct", "result": str(e)[:100]})
            out["error"] = str(e)
            out["error_code"] = "fetch_error"
            out["message"] = str(e)[:500]

    if not out["text"]:
        remaining = [
            ("google_cache", fetch_via_google_cache),
            ("jina", fetch_via_jina),
            ("archive", fetch_via_archive),
        ]
        if jina_first:
            remaining = [r for r in remaining if r[0] != "jina"]
        for fb_name, fb_fn in remaining:
            fb_title, fb_text = fb_fn(url)
            if fb_text.strip() and not _is_cookie_consent(fb_text):
                out["title"] = fb_title or out.get("title", "")
                out["text"] = fb_text
                out["fallback"] = fb_name
                out["error"] = ""
                out["error_code"] = ""
                out["message"] = ""
                fallback_chain.append({"method": fb_name, "result": "ok"})
                break
            else:
                reason = "cookie_consent" if (fb_text.strip() and _is_cookie_consent(fb_text)) else "empty"
                fallback_chain.append({"method": fb_name, "result": reason})
        else:
            if not out["text"]:
                out["error"] = out.get("error") or "All fallbacks failed"
                out["error_code"] = "paywall_blocked"
                out["message"] = out["error"][:500]

    out["fallback_chain"] = fallback_chain
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
