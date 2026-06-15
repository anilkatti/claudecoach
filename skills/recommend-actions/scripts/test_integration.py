import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import load_profile as lp
import render
import apply

PROJECT = {"schema_version": 2, "generated_at": "2026-06-01T00:00:00+00:00",
           "project": {"slug": "s"}, "work_type": "software",
           "task_archetypes": [], "domains": [], "tools_and_materials": [],
           "gaps": [], "provenance": {"sessions_sampled": 5}}
USER = {"schema_version": 2, "generated_at": "2026-06-01T00:00:00+00:00",
        "behavioral_signals": {}, "friction_signals": [], "habits": [],
        "owned_capabilities": {"skills": [], "commands": [], "agents": [], "mcp_servers": []},
        "context_health": {"always_on": {"est_tokens": 0}, "mcp_footprint": {}}, "gaps": []}


def test_load_then_render_then_apply_round_trip(tmp_path):
    # 1. load_profile finds a written profile and splits lanes
    cwd = "/Volumes/proj"
    d = tmp_path / "profiles" / lp.encode_cwd(cwd)
    d.mkdir(parents=True)
    (d / "project.profile.json").write_text(json.dumps(PROJECT))
    (d / "user.profile.json").write_text(json.dumps(USER))
    loaded = lp.load_profiles(cwd, profiles_root=str(tmp_path / "profiles"))
    lanes = lp.split_lanes(loaded["project"], loaded["user"])
    assert set(lanes) == {"acquire", "config", "author", "behavior"}

    # 2. a (hand-built) actions.json renders to HTML with a real card
    actions = {"schema_version": 1, "generated_at": "2026-06-15T00:00:00+00:00",
               "project_slug": loaded["slug"],
               "profile_ref": {"generated_at": PROJECT["generated_at"], "stale": False, "sessions_sampled": 5},
               "indexes": {"capabilities_built_at": "seed", "best_practices_built_at": "seed"},
               "consent": {"network_used": False},
               "actions": [{"id": "cap", "family": "config", "action_type": "capture_context",
                            "priority": "do_now", "title": "Capture test cmd", "rationale": "r",
                            "evidence": [{"signal": "user.friction_signals[0]", "detail": "",
                                          "quote": "session:a \"pytest -q\"", "confidence": 0.6}],
                            "impact_estimate": {"kind": "reexplains_avoided", "value": 4, "basis": "4 of 5"},
                            "source": {"kind": "local_signal", "ref": "", "url": "", "freshness": ""},
                            "effort": "low",
                            "apply": {"kind": "edit_file", "preview": "+ Test: pytest -q",
                                      "reversible": True, "handoff": None, "status": "pending"}}],
               "not_recommended": [], "disclaimer": "d"}
    html = render.render_html(actions)
    assert "Capture test cmd" in html and "pytest -q" in html

    # 3. apply_edit on a context file backs up and writes (reversible)
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# project\n")
    res = apply.apply_edit(str(claude_md), "# project\nTest: pytest -q\n")
    assert "pytest -q" in claude_md.read_text()
    assert open(res["backed_up_to"]).read() == "# project\n"
