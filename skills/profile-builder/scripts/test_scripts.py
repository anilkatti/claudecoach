import json as _json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sessions  # noqa: E402
import inventory  # noqa: E402


# ============================================================ discovery ======

def test_encode_cwd_replaces_non_alnum_with_dash():
    assert sessions.encode_cwd("/Volumes/Sources/claudecoach") == "-Volumes-Sources-claudecoach"


def test_encode_cwd_no_dash_collapsing():
    # nested path with a dotfile dir: each non-alnum char -> its own dash
    assert sessions.encode_cwd("/a/repo/.worktrees/x") == "-a-repo--worktrees-x"


def test_discover_globs_slug_dir(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    proj_root = tmp_path / "projects"
    slug = sessions.encode_cwd(str(repo))
    (proj_root / slug).mkdir(parents=True)
    (proj_root / slug / "a.jsonl").write_text("{}\n")
    (proj_root / slug / "b.jsonl").write_text("{}\n")
    (proj_root / slug / "notes.txt").write_text("ignore me\n")

    found_slug, roots, files = sessions.discover(str(repo), projects_root=str(proj_root))

    assert found_slug == slug
    assert str(repo) in roots  # non-git cwd falls back to [cwd]
    assert sorted(os.path.basename(f) for f in files) == ["a.jsonl", "b.jsonl"]


# ============================================================ sampling =======

def _mani(n, base_chars=5000):
    # newest first by mtime; deterministic paths
    return [{"path": "/p/s%02d.jsonl" % i, "session_id": "s%02d" % i,
             "mtime": float(1000 - i), "approx_chars": base_chars}
            for i in range(n)]


def test_sample_takes_recent_then_seeded_tail():
    chosen, report = sessions.sample(_mani(50), recent=20, tail=15, min_chars=800, seed=0)
    assert len(chosen) == 35
    ids = {c["session_id"] for c in chosen}
    assert {"s%02d" % i for i in range(20)} <= ids  # 20 newest always present
    assert report["recent_taken"] == 20
    assert report["tail_sampled"] == 15
    assert report["tail_skipped"] == 15
    assert report["total"] == 50


def test_sample_is_seed_deterministic():
    a, _ = sessions.sample(_mani(50), seed=7)
    b, _ = sessions.sample(_mani(50), seed=7)
    c, _ = sessions.sample(_mani(50), seed=8)
    assert [x["session_id"] for x in a] == [x["session_id"] for x in b]
    assert [x["session_id"] for x in a] != [x["session_id"] for x in c]


def test_sample_filters_short_sessions():
    chosen, report = sessions.sample(_mani(5, base_chars=100), recent=20, tail=15,
                                     min_chars=800, seed=0)
    assert chosen == []
    assert report["skipped_short"] == 5
    assert report["eligible"] == 0


def test_sample_fewer_than_quota_takes_all():
    chosen, report = sessions.sample(_mani(10), recent=20, tail=15, min_chars=800, seed=0)
    assert len(chosen) == 10
    assert report["tail_sampled"] == 0


# ============================================================ scrubbing ======

@pytest.mark.parametrize("secret,kind", [
    ("sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFF", "anthropic-key"),
    ("AKIAIOSFODNN7EXAMPLE", "aws-key"),
    ("ghp_AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHH1234", "github-token"),
    ("xoxb-" + "1111111111-abcdefghijklmnop", "slack-token"),  # split: fake fixture, avoid secret scanners
    ("AIzaSyA1234567890123456789012345678901234", "google-key"),
])
def test_scrub_redacts_known_secret_formats(secret, kind):
    out = sessions.scrub("before " + secret + " after")
    assert secret not in out
    assert "[REDACTED:%s]" % kind in out


def test_scrub_redacts_env_assignment_and_db_url():
    out = sessions.scrub('DATABASE_URL=postgres://u:p4ssw0rd@host:5432/db\nAPI_KEY="abcd1234efgh"')
    assert "p4ssw0rd" not in out
    assert "abcd1234efgh" not in out


def test_scrub_leaves_clean_text_untouched():
    clean = "Refactor the parser and run pytest -q"
    assert sessions.scrub(clean) == clean


# ============================================================ condense =======

def _write_session(tmp_path):
    entries = [
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "Help me build X. key sk-ant-api03-AAAABBBBCCCCDDDDEEEE"}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "Editing the file now."},
            {"type": "tool_use", "name": "Edit",
             "input": {"file_path": "a.py", "new_string": "Z" * 500}}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "git commit -m wip"}}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "Y" * 2000}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "Now run the tests."}]}},
    ]
    p = tmp_path / "sess.jsonl"
    with open(p, "w") as fh:
        for e in entries:
            fh.write(_json.dumps(e) + "\n")
        fh.write("{ this is not valid json\n")              # malformed -> skipped
        fh.write('\x00{"type":"user","message":{"role":"user",'
                 '"content":[{"type":"text","text":"trailing"}]}}\n')  # null byte
    return str(p)


def test_condense_shapes_and_strips(tmp_path):
    out = sessions.condense(_write_session(tmp_path))
    t = out["condensed_text"]
    assert "USER: Help me build X." in t
    assert "[REDACTED:anthropic-key]" in t
    assert "sk-ant-" not in t
    assert "ASSISTANT: Editing the file now." in t
    assert "TOOL_USE: Edit(a.py) [500 bytes]" in t
    assert "[ToolResult:" in t
    assert "Y" * 50 not in t                       # tool_result body dropped
    assert "Z" * 50 not in t                       # edit body dropped


def test_condense_counts_and_flags(tmp_path):
    out = sessions.condense(_write_session(tmp_path))
    assert out["n_user_msgs"] == 3                 # help / run tests / trailing
    assert out["too_short"] is False
    assert out["facts"]["code_edits"] == 1
    assert out["facts"]["git_commits"] == 1
    assert out["session_id"] == "sess"


def test_condense_marks_trivial_session_too_short(tmp_path):
    p = tmp_path / "tiny.jsonl"
    p.write_text(_json.dumps(
        {"type": "user", "message": {"role": "user",
         "content": [{"type": "text", "text": "hi"}]}}) + "\n")
    out = sessions.condense(str(p))
    assert out["too_short"] is True


def test_condense_single_substantial_prompt_is_usable(tmp_path):
    # A single genuine prompt + real work is analyzable — turn count is NOT the
    # criterion (programmatic/headless runs have one user turn but rich content).
    big = "Reconcile the general ledger to the subledger for FUND_ALPHA. " * 40
    entries = [
        {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": big}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Working on it."}]}},
    ]
    p = tmp_path / "single.jsonl"
    with open(p, "w") as fh:
        for e in entries:
            fh.write(_json.dumps(e) + "\n")
    out = sessions.condense(str(p))
    assert out["n_user_msgs"] == 1
    assert out["too_short"] is False


def test_condense_skips_machinery_and_system_blocks(tmp_path):
    entries = [
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "<command-name>/effort</command-name>"}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "<local-command-stdout>set to max</local-command-stdout>"}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "<system-reminder>be good</system-reminder>"}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "Base directory for this skill: /x/y\n# Big Skill Body\nlots of skill text"}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "Build the real feature please, and verify it."}]}},
    ]
    p = tmp_path / "m.jsonl"
    with open(p, "w") as fh:
        for e in entries:
            fh.write(_json.dumps(e) + "\n")
    out = sessions.condense(str(p))
    assert out["n_user_msgs"] == 1                       # only the genuine prompt
    assert "Build the real feature" in out["condensed_text"]
    assert "/effort" not in out["condensed_text"]
    assert "system-reminder" not in out["condensed_text"]
    assert "Big Skill Body" not in out["condensed_text"]


# ============================================================ prepare ========

def test_prepare_end_to_end(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    proj_root = tmp_path / "projects"
    slug = sessions.encode_cwd(str(repo))
    d = proj_root / slug
    d.mkdir(parents=True)
    big = _json.dumps({"type": "user", "message": {"role": "user",
        "content": [{"type": "text", "text": "build a feature " * 80}]}}) + "\n"
    big += _json.dumps({"type": "user", "message": {"role": "user",
        "content": [{"type": "text", "text": "and verify it " * 80}]}}) + "\n"
    (d / "one.jsonl").write_text(big)
    (d / "two.jsonl").write_text(big)

    out = sessions.prepare(str(repo), recent=20, sample=15, min_chars=800, seed=0,
                           projects_root=str(proj_root))

    assert out["slug"] == slug
    assert out["report"]["total"] == 2
    assert len(out["sessions"]) == 2
    assert all("condensed_text" in s and "too_short" in s for s in out["sessions"])


# ============================================================ inventory ======

def _skill(dirpath, name, desc):
    d = os.path.join(dirpath, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w") as fh:
        fh.write("---\nname: %s\ndescription: %s\n---\n# body\n" % (name, desc))


def test_inventory_labels_sources(tmp_path, monkeypatch):
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    monkeypatch.setenv("HOME", str(home))
    _skill(str(repo / ".claude" / "skills"), "repo-skill", "does repo things")
    _skill(str(home / ".claude" / "skills"), "personal-skill", "does personal things")
    os.makedirs(repo / ".claude" / "commands", exist_ok=True)
    (repo / ".claude" / "commands" / "deploy.md").write_text(
        "---\nname: deploy\ndescription: ship it\n---\nbody\n")
    (repo / ".mcp.json").write_text(_json.dumps({"mcpServers": {"db": {}, "fs": {}}}))

    inv = inventory.inventory(repo=str(repo))

    skills_by_name = {s["name"]: s for s in inv["skills"]}
    assert skills_by_name["repo-skill"]["source"] == "repo"
    assert skills_by_name["repo-skill"]["description"] == "does repo things"
    assert skills_by_name["personal-skill"]["source"] == "personal"
    assert any(c["name"] == "deploy" for c in inv["commands"])
    assert {m["name"] for m in inv["mcp_servers"]} == {"db", "fs"}


def test_inventory_handles_missing_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
    inv = inventory.inventory(repo=str(tmp_path / "empty_repo"))
    assert inv == {"skills": [], "commands": [], "agents": [], "mcp_servers": []}
