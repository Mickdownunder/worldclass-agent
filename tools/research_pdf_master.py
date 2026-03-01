#!/usr/bin/env python3
"""
Generate a PDF from MASTER_DOSSIER.md (Research Council synthesis).
Usage: python3 research_pdf_master.py <project_id>
Writes: research/<project_id>/reports/MASTER_DOSSIER.pdf
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: research_pdf_master.py <project_id>", file=sys.stderr)
        return 2
    project_id = sys.argv[1].strip()
    proj_dir = ROOT / "research" / project_id
    if not proj_dir.is_dir():
        print(f"Project not found: {project_id}", file=sys.stderr)
        return 1

    master_md = proj_dir / "MASTER_DOSSIER.md"
    if not master_md.is_file():
        print("MASTER_DOSSIER.md not found.", file=sys.stderr)
        return 1

    md = master_md.read_text(encoding="utf-8", errors="replace")
    try:
        import markdown
        body_html = markdown.markdown(md, extensions=["extra", "nl2br", "smarty"])
    except ImportError:
        print("markdown not installed. pip install markdown", file=sys.stderr)
        return 1

    css = """
    @page { size: A4; margin: 2cm; }
    body { font-family: system-ui, sans-serif; font-size: 10pt; line-height: 1.5; color: #1e293b; }
    h1 { font-size: 18pt; margin-top: 0; border-bottom: 2px solid #3b82f6; padding-bottom: 0.3em; }
    h2 { font-size: 14pt; margin-top: 1.2em; color: #1e40af; }
    h3 { font-size: 12pt; margin-top: 1em; }
    p { margin: 0.5em 0; }
    ul, ol { margin: 0.5em 0; padding-left: 1.5em; }
    strong { color: #0f172a; }
    """
    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Master Dossier – {project_id}</title>
<style>{css}</style></head>
<body>
<div class="report-body">{body_html}</div>
</body></html>"""

    out_dir = proj_dir / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "MASTER_DOSSIER.pdf"
    try:
        from weasyprint import HTML as WP_HTML
        WP_HTML(string=html, base_url=str(proj_dir)).write_pdf(pdf_path)
        print(str(pdf_path))
        return 0
    except ImportError:
        print("WeasyPrint not installed. pip install weasyprint", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"PDF generation failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
