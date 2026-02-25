#!/usr/bin/env python3
"""
Extract text from a PDF file. Input: path to PDF or URL (downloaded to temp).
Output: JSON { "path"|"url", "text", "error", "page_count" }.

Usage:
  research_pdf_reader.py <path_or_url>
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen, Request


def extract_pdftotext(pdf_path: Path) -> tuple[str, int]:
    """Use pdftotext (poppler-utils) if available."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "pdftotext failed")
    # Page count: pdftotext doesn't give it; use pdfinfo if available
    try:
        r2 = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        n = 0
        for line in r2.stdout.splitlines():
            if line.startswith("Pages:"):
                n = int(line.split(":", 1)[1].strip())
                break
        return result.stdout[:300000], n or 1
    except Exception:
        return result.stdout[:300000], 1


def extract_pypdf(pdf_path: Path) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf not installed; install with: pip install pypdf")
    reader = PdfReader(str(pdf_path))
    n = len(reader.pages)
    parts = []
    for p in reader.pages:
        text = p.extract_text()
        if text:
            parts.append(text)
    return "\n\n".join(parts)[:300000], n


def extract_text(pdf_path: Path) -> tuple[str, int]:
    try:
        return extract_pdftotext(pdf_path)
    except (FileNotFoundError, RuntimeError):
        return extract_pypdf(pdf_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: research_pdf_reader.py <path_or_url>", file=sys.stderr)
        sys.exit(2)
    src = sys.argv[1].strip()
    out = {"path": None, "url": None, "text": "", "page_count": 0, "error": ""}
    pdf_path = None
    if src.startswith("http://") or src.startswith("https://"):
        out["url"] = src
        try:
            req = Request(src, headers={"User-Agent": "OperatorResearch/1.0"})
            with urlopen(req, timeout=30) as r:
                raw = r.read()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(raw)
                pdf_path = Path(f.name)
        except Exception as e:
            out["error"] = str(e)
            print(json.dumps(out, indent=2, ensure_ascii=False))
            sys.exit(1)
    else:
        pdf_path = Path(src).expanduser().resolve()
        out["path"] = str(pdf_path)
        if not pdf_path.is_file():
            out["error"] = "File not found"
            print(json.dumps(out, indent=2, ensure_ascii=False))
            sys.exit(1)
    try:
        text, page_count = extract_text(pdf_path)
        out["text"] = text
        out["page_count"] = page_count
    except Exception as e:
        out["error"] = str(e)
    finally:
        if out.get("url") and pdf_path and pdf_path.exists() and "/tmp" in str(pdf_path):
            try:
                pdf_path.unlink()
            except OSError:
                pass
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
