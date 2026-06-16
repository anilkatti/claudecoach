"""Tests for the profile HTML visualizer. render_html is pure (dict -> HTML
string) so it's unit-testable; the browser-open path is a thin I/O wrapper."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import visualize as viz  # noqa: E402


PROJECT = {
    "kind": "project", "work_type": "software",
    "summary": "A repository for building a Claude coaching plugin.",
    "domains": [{"name": "developer tooling", "weight": 0.9,
                 "evidence": ["session:abc \"build the coach plugin\""]}],
    "tools_and_materials": [{"name": "Python", "weight": 0.8, "evidence": []}],
    "task_archetypes": [{"name": "skill authoring", "weight": 0.7, "evidence": []}],
    "gaps": [{"need": "a recommender", "rationale": "nothing consumes the profile",
              "confidence": 0.6, "evidence": []}],
    "provenance": {"sessions_sampled": 4, "sessions_total": 290,
                   "quotes_verified": 10, "quotes_dropped": 2,
                   "models": {"per_session": "claude-haiku-4-5-20251001",
                              "synthesis": "claude-opus-4-8"}},
    "disclaimer": "LLM-derived from a sample; evidence-verified but nondeterministic.",
}
USER = {
    "kind": "user", "summary": "Works iteratively, tests first, steers strongly.",
    "behavioral_signals": {
        "prompting": {"value": "directive", "evidence": []},
        "planning": {"value": "upfront-plan", "evidence": []},
        "verification": {"value": "tests", "evidence": []},
        "steering": {"value": "strong", "evidence": []},
        "leverage": {"value": "high", "evidence": []}},
    "friction_signals": [{"pattern": "re-explains the git push setup each session",
                          "evidence": ["session:abc \"push over SSH as owner\""],
                          "confidence": 0.7}],
    "strengths": [{"area": "test-driven discipline",
                   "evidence": ["session:abc \"watch it fail first\""]}],
    "gaps": [{"area": "no subagents for parallel work", "rationale": "...",
              "confidence": 0.5, "evidence": []}],
    "context_health": {
        "always_on": {"sources": [{"scope": "global", "path": "~/.claude/CLAUDE.md",
                                   "lines": 90, "chars": 5000}],
                      "total_chars": 5000, "est_tokens": 1250},
        "hooks": [{"event": "UserPromptSubmit", "scope": "global", "count": 1}],
        "duplicate_capabilities": [{"name": "frontend-design", "kind": "skills",
                                    "sources": ["personal", "plugin"]}],
        "overlapping_capabilities": [],
        "mcp_footprint": {"servers": 0, "by_source": {}},
        "unused_capabilities": [{"name": "foo", "kind": "skills", "source": "personal"}]},
    "owned_capabilities": {"skills": [{"name": "x", "description": "y", "source": "personal"}],
                           "commands": [], "agents": [], "mcp_servers": []},
    "disclaimer": "LLM-derived; nondeterministic.",
}


def test_render_html_includes_key_sections():
    html = viz.render_html(PROJECT, USER)
    assert "<html" in html and "</html>" in html
    assert "A repository for building a Claude coaching plugin." in html
    assert "developer tooling" in html
    assert "re-explains the git push setup each session" in html   # friction
    assert "frontend-design" in html                               # duplicate capability
    assert "directive" in html                                     # behavioral signal
    assert "watch it fail first" in html                           # an evidence quote
    assert "1,250" in html or "1250" in html                       # always-on tokens
    assert "nondeterministic" in html.lower()                      # disclaimer


def test_render_html_escapes_user_content():
    html = viz.render_html({"summary": "hi <script>alert(1)</script>"}, {})
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html


def test_render_html_handles_empty_profiles():
    html = viz.render_html({}, {})
    assert "<html" in html and "</html>" in html


def test_quote_keeps_embedded_quotes():
    # The real bug: a quote containing an inner " was cut at the first inner quote.
    assert viz._quote('session:a "He said "hi" and left"') == 'He said "hi" and left'


def test_quote_passthrough_when_no_quotes():
    raw = "context_health.duplicate_capabilities frontend-design [personal, plugin]"
    assert viz._quote(raw) == raw


def test_evidence_drops_junk_and_marker_quotes():
    items = [
        'session:a "So "',                                   # 2 chars after strip -> drop
        'session:b "[…profile-builder truncated 900 chars…]"',  # marker -> drop
        'session:c "a real, illustrative quote"',            # keep
    ]
    out = viz._evidence(items)
    assert "a real, illustrative quote" in out
    assert ">So <" not in out
    assert "truncated" not in out


def test_evidence_empty_when_all_junk():
    assert viz._evidence(['session:a "So "']) == ""


def test_render_uses_shared_theme():
    html = viz.render_html(PROJECT, USER)
    # --acquire exists ONLY in coach_theme.STYLE, not the old inline _TEMPLATE,
    # so this fails before the refactor and passes after.
    assert "--acquire:#3d6fb3" in html
    assert "Fraunces" in html


def test_setup_section_has_no_plus_more_tail():
    many = {**USER, "context_health": {**USER["context_health"],
            "unused_capabilities": [{"name": f"cap{i}", "kind": "skills",
                                     "source": "personal"} for i in range(15)]}}
    html = viz.render_html({}, many)
    assert "more" not in html.split("capabilities owned but unused")[1][:40]  # no "+N more"
    assert "cap14" in html                # full list rendered (in the collapsible details)
    assert "owned but unused" in html
