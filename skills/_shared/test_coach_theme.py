"""Tests for the shared ClaudeCoach HTML theme. Pure string helpers, no I/O."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coach_theme as ct  # noqa: E402


def test_esc_coerces_none_and_escapes():
    assert ct.esc(None) == ""
    assert ct.esc("<b>&") == "&lt;b&gt;&amp;"
    assert ct.esc(12) == "12"


def test_page_is_wellformed_and_carries_tokens():
    html = ct.page("My Title", "<p>hello</p>")
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "<title>My Title</title>" in html
    assert '<div class="wrap"><p>hello</p></div>' in html
    assert "--paper:#f5f0e8" in html        # shared token present
    assert "Fraunces" in html               # shared font present


def test_page_escapes_title():
    html = ct.page("<script>x</script>", "")
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_section_renders_and_omits_empty():
    s = ct.section("Heading", "<p>body</p>", eyebrow="eyebrow text", idx=2)
    assert "<h2>Heading</h2>" in s
    assert "eyebrow text" in s
    assert "<p>body</p>" in s
    assert "animation-delay:0.10s" in s     # 0.05 * idx
    assert ct.section("Heading", "") == ""  # empty body -> no section


def test_callout_wraps_trusted_html():
    assert ct.callout("<b>hi</b>") == '<div class="callout"><b>hi</b></div>'
