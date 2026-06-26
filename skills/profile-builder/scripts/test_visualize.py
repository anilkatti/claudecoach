"""Tests for the profile HTML visualizer. render_html is pure (dict -> HTML
string) so it's unit-testable; the browser-open path is a thin I/O wrapper."""
import os
import re
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


def test_render_uses_new_design_system():
    html = viz.render_html(PROJECT, USER)
    assert "--accent:#bd4d2a" in html        # new token -> kit in use
    assert "Inter" in html and "Fraunces" in html
    assert 'class="mast"' in html            # shared masthead
    assert "ClaudeCoach" in html             # wordmark / footer


def test_render_has_hero_and_sections():
    html = viz.render_html(PROJECT, USER)
    assert "A repository for building a Claude coaching plugin." in html  # standfirst (lead)
    assert "How you work" in html and 'class="sigs"' in html             # signal grid
    assert "directive" in html                                           # a signal value
    assert 'class="bars"' in html and "skill authoring" in html          # weight bars
    assert "watch it fail first" in html                                 # a verified quote
    assert "1,250" in html                                               # stat number
    assert "nondeterministic" in html.lower()                            # disclaimer in footer


def test_render_escapes_and_handles_empty():
    out = viz.render_html({"summary": "hi <script>alert(1)</script>"}, {})
    assert "<script>alert(1)" not in out and "&lt;script&gt;" in out
    assert "<html" in viz.render_html({}, {}) and "</html>" in viz.render_html({}, {})


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
    out = viz._first_evidence(items)
    assert "a real, illustrative quote" in out
    assert "So" not in out
    assert "truncated" not in out


def test_evidence_empty_when_all_junk():
    assert viz._first_evidence(['session:a "So "']) == ""


def test_setup_section_collapsible_unused_no_more_tail():
    many = {**USER, "context_health": {**USER["context_health"],
            "unused_capabilities": [{"name": f"cap{i}", "kind": "skills",
                                     "source": "personal"} for i in range(15)]}}
    html = viz.render_html({}, many)
    assert "cap14" in html and "owned but unused" in html
    assert not re.search(r"\+\d+ more", html)   # no truncation tail at all


def test_gap_rationale_renders_as_block_not_inline_after_title():
    # Regression: the gap title (<b>) was followed by an INLINE <span> rationale,
    # so they ran together ("...injection)The same remote-run..."). The rationale
    # must be a block element so it drops onto its own line below the title.
    html = viz._sg_list(
        [{"area": "Durable runbook capture", "rationale": "re-explained each session",
          "evidence": []}], "area", with_why=True)
    assert "<span class=\"d\">" not in html              # not inline anymore
    assert "</b><div class=\"d\"" in html                # title closes, block begins
    assert "re-explained each session" in html
