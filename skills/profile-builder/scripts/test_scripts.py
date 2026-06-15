import io
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


def test_sample_backfills_past_nonanalyzable_to_fill_quota():
    # When the most-recent sessions are trivial, the recent quota backfills with
    # the next analyzable ones rather than wasting slots on noise.
    trivial = {"s00", "s01", "s02"}   # s00 is newest
    chosen, report = sessions.sample(
        _mani(10), recent=3, tail=0, min_chars=800, seed=0,
        analyzable=lambda m: m["session_id"] not in trivial)
    assert [c["session_id"] for c in chosen] == ["s03", "s04", "s05"]
    assert report["recent_taken"] == 3
    assert report["trivial_skipped"] == 3


def test_sample_default_predicate_keeps_everything_analyzable():
    # No predicate => old behavior: nothing is treated as trivial.
    chosen, report = sessions.sample(_mani(5), recent=20, tail=15, min_chars=800, seed=0)
    assert len(chosen) == 5
    assert report["trivial_skipped"] == 0


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


def test_condense_single_prompt_without_work_is_skipped(tmp_path):
    # A lone prompt that produced no durable work (no files written, no commits)
    # reveals little about HOW someone works — no steering, no iteration, no
    # verification — so it's excluded from profiling.
    big = "Reconcile the general ledger to the subledger for FUND_ALPHA. " * 40
    entries = [
        {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": big}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Here's how I'd approach it."}]}},
    ]
    p = tmp_path / "single.jsonl"
    with open(p, "w") as fh:
        for e in entries:
            fh.write(_json.dumps(e) + "\n")
    out = sessions.condense(str(p))
    assert out["n_user_msgs"] == 1
    assert out["too_short"] is True


def test_condense_single_prompt_with_real_work_is_kept(tmp_path):
    # But a one-shot/headless run that actually produced artifacts IS analyzable
    # — turn count alone is not the criterion.
    big = "Reconcile the ledger and write the report. " * 40
    entries = [
        {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": big}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Write", "input": {"file_path": "report.md", "content": "x" * 100}}]}},
    ]
    p = tmp_path / "single_work.jsonl"
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


def test_prepare_excludes_trivial_single_prompt(tmp_path):
    # A trivial single-prompt session must not occupy a sample slot; a
    # substantive multi-turn session with work is kept.
    repo = tmp_path / "repo"
    repo.mkdir()
    proj_root = tmp_path / "projects"
    slug = sessions.encode_cwd(str(repo))
    d = proj_root / slug
    d.mkdir(parents=True)
    sub = (_json.dumps({"type": "user", "message": {"role": "user", "content": [
                {"type": "text", "text": "build a feature " * 80}]}}) + "\n"
           + _json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Write", "input": {"file_path": "a.py", "content": "x" * 200}}]}}) + "\n"
           + _json.dumps({"type": "user", "message": {"role": "user", "content": [
                {"type": "text", "text": "now verify it " * 80}]}}) + "\n")
    (d / "sub.jsonl").write_text(sub)
    triv = _json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "text", "text": "just one quick question here " * 40}]}}) + "\n"
    (d / "triv.jsonl").write_text(triv)

    out = sessions.prepare(str(repo), recent=20, sample=15, min_chars=800, seed=0,
                           projects_root=str(proj_root))

    ids = [s["session_id"] for s in out["sessions"]]
    assert "sub" in ids
    assert "triv" not in ids
    assert out["report"]["trivial_skipped"] >= 1


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


# ================================================= friction / neutral facts ===
# v2: the sensor must work for non-developers, so "work" is measured as
# artifacts of ANY type (not just code), plus deterministic friction signals
# (tool errors, wall-clock duration). Grounded in the real session schema:
# entries carry an ISO8601 `timestamp`; tool_result blocks carry `is_error`.

def _write_friction_session(tmp_path):
    entries = [
        {"type": "user", "timestamp": "2026-06-15T10:00:00.000Z",
         "message": {"role": "user", "content": [
             {"type": "text", "text": "Reconcile the ledger and update the workbook."}]}},
        {"type": "assistant", "timestamp": "2026-06-15T10:00:05.000Z",
         "message": {"role": "assistant", "content": [
             {"type": "tool_use", "name": "Write", "input": {"file_path": "report.md", "content": "Z" * 50}},
             {"type": "tool_use", "name": "Edit", "input": {"file_path": "data/ledger.csv", "old_string": "a", "new_string": "b"}},
             {"type": "tool_use", "name": "Edit", "input": {"file_path": "app.py", "old_string": "a", "new_string": "b"}},
             {"type": "tool_use", "name": "Write", "input": {"file_path": "config.yaml", "content": "k: v"}},
             {"type": "tool_use", "name": "Write", "input": {"file_path": "Makefile", "content": "all:"}}]}},
        {"type": "user", "timestamp": "2026-06-15T10:05:00.000Z",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "boom"}]}},
        {"type": "user", "timestamp": "2026-06-15T10:10:00.000Z",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "t2", "content": "ok"},
             {"type": "text", "text": "Now also export a summary, please."}]}},
    ]
    p = tmp_path / "fr.jsonl"
    with open(p, "w") as fh:
        for e in entries:
            fh.write(_json.dumps(e) + "\n")
    return str(p)


def test_condense_counts_tool_errors(tmp_path):
    out = sessions.condense(_write_friction_session(tmp_path))
    assert out["facts"]["tool_errors"] == 1
    assert out["truncated"] is False


def test_condense_buckets_artifacts_by_material_type(tmp_path):
    # An accountant editing a .csv and a .md is doing real work; v1 counted
    # only "code_edits" and would score this session as empty.
    a = sessions.condense(_write_friction_session(tmp_path))["facts"]["artifacts"]
    assert a["doc"] == 1       # report.md
    assert a["data"] == 1      # data/ledger.csv
    assert a["code"] == 1      # app.py
    assert a["config"] == 1    # config.yaml
    assert a["other"] == 1     # Makefile (no extension)


def test_condense_computes_duration_seconds(tmp_path):
    out = sessions.condense(_write_friction_session(tmp_path))
    assert out["facts"]["duration_seconds"] == 600   # 10:00:00 -> 10:10:00


def test_condense_duration_zero_without_timestamps(tmp_path):
    p = tmp_path / "nots.jsonl"
    p.write_text(_json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "text", "text": "hello there, please do the thing " * 5}]}}) + "\n")
    out = sessions.condense(str(p))
    assert out["facts"]["duration_seconds"] == 0


def test_condense_truncates_oversized_text(tmp_path):
    # Many large turns sum past the total cap even though each block is under
    # the per-block limit; truncation must be flagged, never silent.
    entries = [{"type": "user", "message": {"role": "user", "content": [
        {"type": "text", "text": ("chunk%02d " % i) + ("z" * 18000)}]}} for i in range(12)]
    p = tmp_path / "big.jsonl"
    with open(p, "w") as fh:
        for e in entries:
            fh.write(_json.dumps(e) + "\n")
    out = sessions.condense(str(p))
    assert out["truncated"] is True
    assert len(out["condensed_text"]) <= sessions._MAX_CONDENSED + 80


# ===================================================== quote verification ===
# v2 fixes the broken evidence contract: synthesis may only cite quotes that
# provably appear in a condensed transcript. This is the deterministic guard.

def test_verify_quotes_keeps_real_substrings_drops_fabrications():
    texts = ["USER: Reconcile the ledger\nASSISTANT: done", "USER: ship the parser"]
    verified, dropped = sessions.verify_quotes(
        ["Reconcile the ledger", "ship the parser", "a quote nobody ever said"], texts)
    assert set(verified) == {"Reconcile the ledger", "ship the parser"}
    assert dropped == ["a quote nobody ever said"]


def test_verify_quotes_normalizes_whitespace():
    # Models reflow whitespace when quoting; matching must be whitespace-robust.
    verified, dropped = sessions.verify_quotes(
        ["Reconcile   the\nledger"], ["USER: Reconcile the ledger now"])
    assert verified == ["Reconcile   the\nledger"]
    assert dropped == []


def test_cli_verify_filters_quotes(monkeypatch, capsys):
    # The orchestrator pipes {quotes, texts} in; the guard returns which quotes
    # provably appear in a transcript so synthesis can cite only those.
    payload = {"quotes": ["real one", "totally fabricated"],
               "texts": ["here is the real one, indeed"]}
    monkeypatch.setattr(sys, "stdin", io.StringIO(_json.dumps(payload)))
    rc = sessions.main(["verify"])
    assert rc == 0
    out = _json.loads(capsys.readouterr().out)
    assert out["verified"] == ["real one"]
    assert out["dropped"] == ["totally fabricated"]
