import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import load_profile as lp

PROJECT = {
    "schema_version": 2, "kind": "project", "generated_at": "2026-06-01T00:00:00+00:00",
    "project": {"slug": "s", "root": "/x"},
    "work_type": "software",
    "domains": [{"name": "billing", "weight": 0.8, "evidence": ["session:a \"q\""]}],
    "tools_and_materials": [{"name": "python", "weight": 0.7, "evidence": []}],
    "task_archetypes": [{"name": "PR review", "weight": 0.6, "evidence": []}],
    "gaps": [{"need": "pr triage", "rationale": "...", "confidence": 0.7, "evidence": []}],
    "provenance": {"sessions_sampled": 12},
}
USER = {
    "schema_version": 2, "kind": "user", "generated_at": "2026-06-01T00:00:00+00:00",
    "behavioral_signals": {"planning": {"value": "none", "evidence": []}},
    "friction_signals": [{"pattern": "re-explains test cmd", "evidence": [], "confidence": 0.6}],
    "habits": [{"label": "accepts unread", "polarity": "holding-back", "evidence": "3 of 12", "detail": ""}],
    "owned_capabilities": {"skills": [{"name": "frontend-design", "description": "", "source": "plugin"}],
                           "commands": [], "agents": [], "mcp_servers": []},
    "context_health": {"always_on": {"total_chars": 5000, "est_tokens": 1300, "sources": []},
                       "hooks": [], "duplicate_capabilities": [], "overlapping_capabilities": [],
                       "mcp_footprint": {"servers": 0, "by_source": {}}, "unused_capabilities": []},
    "gaps": [{"area": "verification habit", "rationale": "...", "confidence": 0.5, "evidence": []}],
}


def _write_profile(tmp_path, cwd="/Volumes/x"):
    slug = lp.encode_cwd(cwd)
    d = tmp_path / "profiles" / slug
    d.mkdir(parents=True)
    (d / "project.profile.json").write_text(json.dumps(PROJECT))
    (d / "user.profile.json").write_text(json.dumps(USER))
    return cwd, str(d)


def test_encode_cwd_matches_profile_builder_rule():
    # Same rule as profile-builder: every non-alphanumeric char becomes '-'
    assert lp.encode_cwd("/Volumes/Sources/cc") == "-Volumes-Sources-cc"


def test_load_profiles_missing(tmp_path):
    res = lp.load_profiles("/no/such/cwd", profiles_root=str(tmp_path / "profiles"))
    assert res["error"] == "no_profile"


def test_load_profiles_ok(tmp_path):
    cwd, _ = _write_profile(tmp_path)
    res = lp.load_profiles(cwd, profiles_root=str(tmp_path / "profiles"))
    assert "error" not in res
    assert res["project"]["work_type"] == "software"
    assert res["user"]["behavioral_signals"]["planning"]["value"] == "none"


def test_freshness_fresh():
    f = lp.freshness(PROJECT, now_iso="2026-06-10T00:00:00+00:00", max_age_days=14)
    assert f["age_days"] == 9 and f["stale"] is False


def test_freshness_stale():
    f = lp.freshness(PROJECT, now_iso="2026-07-01T00:00:00+00:00", max_age_days=14)
    assert f["stale"] is True


def test_split_lanes_has_four_lanes_with_expected_keys():
    lanes = lp.split_lanes(PROJECT, USER)
    assert set(lanes) == {"acquire", "config", "author", "behavior"}
    assert lanes["acquire"]["work_type"] == "software"
    assert lanes["acquire"]["user_gaps"] == USER["gaps"]
    assert lanes["acquire"]["owned_capabilities"] == USER["owned_capabilities"]
    assert lanes["config"]["context_health"] == USER["context_health"]
    assert lanes["author"]["task_archetypes"] == PROJECT["task_archetypes"]
    assert lanes["behavior"]["habits"] == USER["habits"]


def test_cli_emits_lanes_json(tmp_path):
    cwd, _ = _write_profile(tmp_path)
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "load_profile.py"),
         cwd, "--profiles-root", str(tmp_path / "profiles"),
         "--now", "2026-06-10T00:00:00+00:00"],
        capture_output=True, text=True, check=True).stdout
    doc = json.loads(out)
    assert doc["slug"] == lp.encode_cwd(cwd)
    assert doc["freshness"]["stale"] is False
    assert set(doc["lanes"]) == {"acquire", "config", "author", "behavior"}


def test_cli_missing_profile_emits_error(tmp_path):
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "load_profile.py"),
         "/no/such/cwd", "--profiles-root", str(tmp_path / "profiles")],
        capture_output=True, text=True).stdout
    assert json.loads(out)["error"] == "no_profile"


def test_freshness_handles_naive_generated_at():
    # naive generated_at (no tz offset) must NOT crash the default tz-aware now path
    naive = {"generated_at": "2026-06-01T00:00:00"}
    f = lp.freshness(naive, now_iso="2026-06-10T00:00:00+00:00")
    assert f["age_days"] == 9 and f["stale"] is False


def test_freshness_boundary():
    base = {"generated_at": "2026-06-01T00:00:00+00:00"}
    assert lp.freshness(base, now_iso="2026-06-15T00:00:00+00:00", max_age_days=14)["stale"] is False  # exactly 14 days
    assert lp.freshness(base, now_iso="2026-06-16T00:00:00+00:00", max_age_days=14)["stale"] is True   # 15 days


def test_load_profiles_bad_json(tmp_path):
    cwd = "/Volumes/x"
    d = tmp_path / "profiles" / lp.encode_cwd(cwd)
    d.mkdir(parents=True)
    (d / "project.profile.json").write_text("{ not valid json")
    (d / "user.profile.json").write_text("{}")
    res = lp.load_profiles(cwd, profiles_root=str(tmp_path / "profiles"))
    assert res["error"] == "bad_json"
