"""Unit tests for tools/research_web_reader.py."""
import pytest

pytest.importorskip("bs4")

from tools.research_web_reader import (
    _sanitize_html_for_lxml,
    _detect_paywall,
    _is_cookie_consent,
    extract_with_bs4,
)
from bs4 import BeautifulSoup


def test_sanitize_html_removes_null_bytes():
    """_sanitize_html_for_lxml() removes NULL bytes."""
    raw = "Hello\x00World"
    assert "\x00" not in _sanitize_html_for_lxml(raw)
    assert "Hello" in _sanitize_html_for_lxml(raw) and "World" in _sanitize_html_for_lxml(raw)


def test_sanitize_html_removes_control_chars():
    """_sanitize_html_for_lxml() removes control characters."""
    raw = "a\x01b\x0cc\x1fd"
    out = _sanitize_html_for_lxml(raw)
    assert out == "abc" or "\x01" not in out and "\x0c" not in out


def test_sanitize_html_preserves_newlines():
    """_sanitize_html_for_lxml() preserves \\n and \\t."""
    raw = "line1\nline2\t tab"
    assert "\n" in _sanitize_html_for_lxml(raw)
    assert "line1" in _sanitize_html_for_lxml(raw)


def test_detect_paywall_short_body():
    """_detect_paywall() returns True for very short body text."""
    html = "<html><body><p>Only 50 chars here.</p></body></html>"
    assert _detect_paywall(html) is True


def test_detect_paywall_long_body_no_pattern():
    """_detect_paywall() returns False for long body without paywall pattern."""
    html = "<html><body><p>" + "x" * 300 + "</p></body></html>"
    assert _detect_paywall(html) is False


def test_detect_paywall_pattern():
    """_detect_paywall() returns True when paywall pattern in HTML."""
    html = "<html><body><p>" + "x" * 300 + "</p><div class='paywall'>Subscribe</div></body></html>"
    assert _detect_paywall(html) is True


def test_is_cookie_consent_short():
    """_is_cookie_consent() returns True for very short text."""
    assert _is_cookie_consent("") is True
    assert _is_cookie_consent("x" * 10) is True


def test_is_cookie_consent_google_phrase():
    """_is_cookie_consent() returns True when consent phrase in text."""
    text = "Before you continue to Google please accept cookies. " + "x" * 100
    assert _is_cookie_consent(text) is True


def test_is_cookie_consent_normal_article():
    """_is_cookie_consent() returns False for normal article-like text."""
    text = "This is a normal article with enough content and no consent banner. " * 10
    assert _is_cookie_consent(text) is False


def test_extract_with_bs4_title_and_body():
    """extract_with_bs4() extracts title and body text."""
    html = "<html><head><title>My Title</title></head><body><p>Paragraph one.</p><p>Paragraph two.</p></body></html>"
    title, text = extract_with_bs4(html, BeautifulSoup)
    assert title == "My Title"
    assert "Paragraph one" in text and "Paragraph two" in text


def test_extract_with_bs4_empty_body():
    """extract_with_bs4() returns empty text for body with only script/style."""
    html = "<html><head><title>T</title></head><body><script>x</script><style>y</style></body></html>"
    title, text = extract_with_bs4(html, BeautifulSoup)
    assert title == "T"
    assert text.strip() == "" or len(text.strip()) < 20
