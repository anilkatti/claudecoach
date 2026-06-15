"""Tests for the config-health probe (Goal 2 sensor: surface context-bloat /
contradiction *signals*, collect-don't-judge). Deterministic plumbing only."""
import json as _json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import context_health as ch  # noqa: E402
import sessions  # noqa: E402


# ----------------------------------------------------------- always-on context

def test_always_on_counts_existing_context_files(tmp_path):
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    slug = sessions.encode_cwd(str(repo))
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "CLAUDE.md").write_text("a\nb\nc\n")           # 3 lines
    (repo).mkdir()
    (repo / "CLAUDE.md").write_text("x\ny\n")                          # 2 lines
    mem = home / ".claude" / "projects" / slug / "memory"
    mem.mkdir(parents=True)
    (mem / "MEMORY.md").write_text("only one line\n")                  # 1 line

    out = ch.always_on_context(str(home), str(repo), slug)

    scopes = {s["scope"]: s for s in out["sources"]}
    assert scopes["global"]["lines"] == 3
    assert scopes["repo"]["lines"] == 2
    assert scopes["memory"]["lines"] == 1
    assert out["total_chars"] > 0
    assert out["est_tokens"] == out["total_chars"] // 4


def test_always_on_skips_absent_files(tmp_path):
    out = ch.always_on_context(str(tmp_path / "h"), str(tmp_path / "r"), "slug")
    assert out["sources"] == []
    assert out["total_chars"] == 0
    assert out["est_tokens"] == 0


# ------------------------------------------------------------------------ hooks

def test_hooks_counts_command_hooks_per_event(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(_json.dumps({"hooks": {
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "x"}]}],
        "PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "y"}, {"type": "command", "command": "z"}]}],
    }}))

    by_event = {(h["event"], h["scope"]): h["count"]
                for h in ch.hooks(str(home), str(tmp_path / "norepo"))}
    assert by_event[("UserPromptSubmit", "global")] == 1
    assert by_event[("PreToolUse", "global")] == 2


def test_hooks_empty_when_no_settings(tmp_path):
    assert ch.hooks(str(tmp_path / "h"), str(tmp_path / "r")) == []


# ----------------------------------------------------- duplicate capabilities

def test_find_duplicate_capabilities_flags_same_name_across_levels():
    inv = {"skills": [{"name": "foo", "source": "personal"},
                      {"name": "foo", "source": "plugin"},
                      {"name": "bar", "source": "personal"}],
           "commands": [], "agents": [], "mcp_servers": []}
    dups = ch.find_duplicate_capabilities(inv)
    assert len(dups) == 1
    assert dups[0]["name"] == "foo"
    assert sorted(dups[0]["sources"]) == ["personal", "plugin"]


# ---------------------------------------------------- overlapping capabilities

def test_find_overlapping_ignores_same_name_duplicates():
    # The same skill installed twice is a *duplicate* (reported separately), not
    # an overlapping pair — flagging it here would double-count the signal.
    inv = {"skills": [
        {"name": "frontend-design", "description": "create distinctive production-grade frontend interfaces", "source": "personal"},
        {"name": "frontend-design", "description": "create distinctive production-grade frontend interfaces", "source": "plugin"}],
        "commands": [], "agents": [], "mcp_servers": []}
    assert ch.find_overlapping_capabilities(inv) == []


def test_find_overlapping_flags_near_duplicate_descriptions():
    inv = {"skills": [
        {"name": "a", "description": "reconcile the general ledger to subledger", "source": "personal"},
        {"name": "b", "description": "reconcile general ledger against the subledger", "source": "plugin"},
        {"name": "c", "description": "draw a frontend dashboard with charts", "source": "personal"}],
        "commands": [], "agents": [], "mcp_servers": []}
    pairs = ch.find_overlapping_capabilities(inv, threshold=0.6)
    flagged = {tuple(sorted((p["a"], p["b"]))) for p in pairs}
    assert ("a", "b") in flagged
    assert not any("c" in pair for pair in flagged)


# --------------------------------------------------------------- mcp footprint

def test_mcp_footprint_counts_servers():
    inv = {"skills": [], "commands": [], "agents": [],
           "mcp_servers": [{"name": "db", "source": "repo"},
                           {"name": "fs", "source": "personal"}]}
    fp = ch.mcp_footprint(inv)
    assert fp["servers"] == 2


# ----------------------------------------------------------- unused (Goal 1/2)

def test_unused_capabilities_are_owned_but_never_seen():
    inv = {"skills": [{"name": "used", "source": "personal"},
                      {"name": "dead", "source": "plugin"}],
           "commands": [], "agents": [], "mcp_servers": []}
    unused = ch.unused_capabilities(inv, {"used"})
    names = {u["name"] for u in unused}
    assert names == {"dead"}


# ------------------------------------------------------------- health() top API

def test_health_assembles_sections_and_handles_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
    out = ch.health(str(tmp_path / "empty_repo"))
    assert set(out) >= {"always_on", "hooks", "duplicate_capabilities",
                        "overlapping_capabilities", "mcp_footprint",
                        "unused_capabilities"}
    assert out["always_on"]["total_chars"] == 0
    assert out["hooks"] == []
    assert out["duplicate_capabilities"] == []
