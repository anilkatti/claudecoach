import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import render

DOC = {
    "schema_version": 1, "generated_at": "2026-06-15T00:00:00+00:00",
    "project_slug": "-Volumes-x",
    "profile_ref": {"generated_at": "2026-06-01T00:00:00+00:00", "stale": False, "sessions_sampled": 12},
    "indexes": {"capabilities_fetched_at": "2026-06-10", "best_practices_built_at": "2026-06-10"},
    "consent": {"network_used": True},
    "actions": [
        {"id": "capture-coa", "family": "config", "action_type": "capture_context",
         "priority": "do_now", "title": "Capture your test command in CLAUDE.md",
         "rationale": "You re-explain the test command most sessions.",
         "evidence": [{"signal": "user.friction_signals[0]", "detail": "re-states test cmd",
                       "quote": "session:a \"the test command is pytest -q\"", "confidence": 0.6}],
         "impact_estimate": {"kind": "reexplains_avoided", "value": 8, "basis": "8 of 12 sampled sessions"},
         "source": {"kind": "local_signal", "ref": "", "url": "", "freshness": ""},
         "effort": "low",
         "apply": {"kind": "edit_file", "preview": "+ Test command: pytest -q",
                   "reversible": True, "handoff": None, "status": "pending"}},
        {"id": "install-pr-triage", "family": "acquire", "action_type": "install_skill",
         "priority": "consider", "title": "Install pr-triage",
         "rationale": "Heavy PR review, no triage skill.",
         "evidence": [{"signal": "project.gaps[0]", "detail": "", "quote": "session:b \"review this PR\"", "confidence": 0.7}],
         "impact_estimate": {"kind": "qualitative", "value": 0, "basis": ""},
         "source": {"kind": "curated_index", "ref": "capabilities_index:pr-triage",
                    "url": "https://example.com/pr-triage", "freshness": "built_at 2026-06-10"},
         "effort": "low",
         "apply": {"kind": "run_command", "preview": "ln -s ...", "reversible": True,
                   "handoff": None, "status": "pending"}},
    ],
    "not_recommended": [{"considered": "a fancy skill", "why_dropped": "no source found"}],
    "disclaimer": "LLM-derived; nondeterministic.",
}


def test_group_by_priority():
    g = render.group_by_priority(DOC["actions"])
    assert [a["id"] for a in g["do_now"]] == ["capture-coa"]
    assert [a["id"] for a in g["consider"]] == ["install-pr-triage"]
    assert g["fyi"] == []


def test_console_shows_titles_evidence_and_source():
    txt = render.render_console(DOC)
    assert "Capture your test command" in txt
    assert "the test command is pytest -q" in txt          # evidence quote shown
    assert "built_at 2026-06-10" in txt                     # research freshness shown
    assert "no source found" in txt                         # not_recommended ledger shown


def test_html_has_sections_and_escapes():
    html = render.render_html(DOC)
    for needle in ("Do now", "Consider", "Capture your test command",
                   "the test command is pytest -q", "built_at 2026-06-10",
                   "Considered but not recommended", "nondeterministic"):
        assert needle in html
    # HTML-escape angle brackets in user-derived text
    assert "<script>" not in render.render_html({**DOC, "actions": [
        {**DOC["actions"][0], "title": "<script>x</script>"}]})


def test_handles_empty_actions():
    html = render.render_html({**DOC, "actions": [], "not_recommended": []})
    assert "No actions" in html


def test_cli_writes_html(tmp_path):
    import json
    import subprocess
    src = tmp_path / "actions.json"
    src.write_text(json.dumps(DOC))
    out = tmp_path / "actions.html"
    subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "render.py"),
         str(src), "--html-out", str(out), "--no-open"], check=True)
    assert "Do now" in out.read_text()


def test_html_drops_dangerous_url_scheme():
    doc = {**DOC, "actions": [{**DOC["actions"][1],
        "source": {"kind": "live_web", "ref": "", "url": "javascript:alert(1)", "freshness": ""}}]}
    out = render.render_html(doc)
    assert "javascript:alert(1)" not in out  # dangerous scheme never becomes a link


def test_impact_value_none_is_not_literal_none():
    doc = {**DOC, "actions": [{**DOC["actions"][0],
        "impact_estimate": {"kind": "tokens_saved", "value": None, "basis": "b"}}]}
    out = render.render_html(doc)
    assert "None tokens_saved" not in out  # None coerced to '', not the string 'None'


def test_html_shows_capabilities_fetched_at():
    html = render.render_html(DOC)
    assert "capabilities 2026-06-10" in html
