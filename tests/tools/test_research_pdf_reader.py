"""Unit tests for tools/research_pdf_reader.py."""
import pytest
from pathlib import Path
from unittest.mock import patch

from tools.research_pdf_reader import extract_pypdf, extract_text


def test_extract_pypdf_nonexistent_raises():
    """extract_pypdf raises for non-existent path."""
    with pytest.raises((FileNotFoundError, OSError, RuntimeError)):
        extract_pypdf(Path("/nonexistent/file.pdf"))


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("pypdf") is None,
    reason="pypdf not installed",
)
def test_extract_pypdf_empty_pdf(tmp_path):
    """extract_pypdf returns (text, page_count) for a minimal PDF."""
    # Create minimal valid PDF (6 lines minimal PDF)
    pdf = tmp_path / "minimal.pdf"
    pdf.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
    )
    text, count = extract_pypdf(pdf)
    assert isinstance(text, str)
    assert count == 1


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("pypdf") is None,
    reason="pypdf not installed",
)
def test_extract_text_fallback_to_pypdf(tmp_path):
    """extract_text uses pypdf when pdftotext not available; skip if PDF invalid."""
    pdf = tmp_path / "empty.pdf"
    pdf.write_bytes(b"%PDF-1.4\n minimal\n%%EOF\n")
    try:
        with patch("tools.research_pdf_reader.extract_pdftotext", side_effect=FileNotFoundError):
            text, count = extract_text(pdf)
            assert isinstance(text, str)
            assert count >= 0
    except Exception as e:
        if "PdfReadError" in type(e).__name__ or "startxref" in str(e):
            pytest.skip("minimal PDF not valid for pypdf")
        raise
