"""The pre-push version-bump guard: unit logic + end-to-end through `git push`.

Two layers, both offline and model-free:

  - Unit tests pin the pure string/JSON helpers in `scripts/bump_plugin_version.py`
    (bump arithmetic, minimal-diff version rewrite, zero-sha detection).
  - One integration test builds a throwaway repo with a bare "remote", installs
    the real hook via `core.hooksPath`, and drives real `git push`es to prove the
    guard's three outcomes: bump-and-abort on an un-bumped payload change, pass
    on an already-bumped change, and pass on a non-payload change.

The guard only ever acts on the publish branch (`main`); the integration repo
uses that branch so the e2e path is exercised.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import helpers

sys.path.insert(0, str(helpers.REPO_ROOT / "scripts"))
import bump_plugin_version as bpv  # noqa: E402


# --------------------------------------------------------------------------- #
# Unit: pure helpers                                                          #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("version,expected", [
    ("1.0.0", "1.0.1"),
    ("1.2.9", "1.2.10"),
    ("0.0.0", "0.0.1"),
    ("2.10.99", "2.10.100"),
])
def test_bump_patch_increments_only_the_patch(version, expected):
    assert bpv.bump_patch(version) == expected


@pytest.mark.parametrize("bad", ["1.0", "1", "v1.0.0", "1.0.0-rc1", "1.0.x", ""])
def test_bump_patch_rejects_non_semver(bad):
    with pytest.raises(ValueError):
        bpv.bump_patch(bad)


def test_version_from_json_text_reads_the_field():
    assert bpv.version_from_json_text('{"version": "3.4.5"}') == "3.4.5"


def test_set_version_rewrites_only_the_version_value():
    original = (
        '{\n'
        '  "name": "claudecoach",\n'
        '  "version": "1.0.0",\n'
        '  "keywords": ["version", "1.0.0 lookalike"]\n'
        '}\n'
    )
    updated = bpv.set_version_in_json_text(original, "1.0.1")
    # The version field flips...
    assert json.loads(updated)["version"] == "1.0.1"
    # ...and nothing else does: only that one line differs, byte-for-byte.
    diff = [(a, b) for a, b in zip(original.splitlines(), updated.splitlines()) if a != b]
    assert diff == [('  "version": "1.0.0",', '  "version": "1.0.1",')]
    # The decoy "1.0.0 lookalike" keyword is untouched.
    assert "1.0.0 lookalike" in updated


def test_set_version_requires_exactly_one_version_field():
    with pytest.raises(ValueError):
        bpv.set_version_in_json_text('{"name": "x"}', "1.0.1")


@pytest.mark.parametrize("sha,zero", [
    ("0" * 40, True),
    ("0" * 64, True),
    ("", True),
    ("0000000000000000000000000000000000000001", False),
    ("abc123", False),
])
def test_is_zero_detects_deletion_and_new_branch_shas(sha, zero):
    assert bpv.is_zero(sha) is zero


# --------------------------------------------------------------------------- #
# Integration: the real hook, driven by real `git push`                       #
# --------------------------------------------------------------------------- #

def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def _read_version(repo: Path) -> str:
    return json.loads((repo / ".claude-plugin" / "plugin.json").read_text())["version"]


def _remote_version(remote: Path, work: Path) -> str:
    """The version as it exists on the bare remote's main branch."""
    blob = _git(work, "show", "main:.claude-plugin/plugin.json")  # local main tracks pushed state after success
    return json.loads(blob.stdout)["version"]


@pytest.fixture
def repo_pair(tmp_path: Path) -> tuple[Path, Path]:
    """A work repo (hook installed, on `main`) wired to a bare `remote.git`.

    Mirrors the real layout the hook depends on: a `.claude-plugin/plugin.json`
    at 1.0.0, a `skills/` payload dir, and the real hook + bump script copied in
    with `core.hooksPath` pointed at them (absolute, exactly as install-hooks.sh
    does). An initial commit is pushed so the remote has a 1.0.0 baseline.
    """
    work = tmp_path / "work"
    remote = tmp_path / "remote.git"
    (work / ".claude-plugin").mkdir(parents=True)
    (work / "skills" / "demo").mkdir(parents=True)
    (work / "scripts" / "hooks").mkdir(parents=True)

    (work / ".claude-plugin" / "plugin.json").write_text(
        '{\n  "name": "claudecoach",\n  "version": "1.0.0"\n}\n')
    (work / "skills" / "demo" / "SKILL.md").write_text("# demo\noriginal\n")
    (work / "README.md").write_text("# readme\n")

    # Copy the real hook + bump script under test into the synthetic repo.
    shutil.copy(helpers.REPO_ROOT / "scripts" / "bump_plugin_version.py",
                work / "scripts" / "bump_plugin_version.py")
    shutil.copy(helpers.REPO_ROOT / "scripts" / "hooks" / "pre-push",
                work / "scripts" / "hooks" / "pre-push")
    (work / "scripts" / "hooks" / "pre-push").chmod(0o755)

    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "Test")
    _git(work, "config", "commit.gpgsign", "false")
    _git(work, "config", "core.hooksPath", str(work / "scripts" / "hooks"))
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "initial")

    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    _git(work, "remote", "add", "origin", str(remote))
    _git(work, "push", "-q", "-u", "origin", "main")  # remote baseline at 1.0.0
    return work, remote


def test_payload_change_without_bump_is_blocked_then_bumped_and_pushable(repo_pair):
    work, remote = repo_pair
    (work / "skills" / "demo" / "SKILL.md").write_text("# demo\nedited\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "edit demo skill")

    # First push: guard fires — aborts, but bumps + commits the version for us.
    blocked = _git(work, "push", "origin", "main", check=False)
    assert blocked.returncode != 0, blocked.stdout + blocked.stderr
    assert "1.0.0 -> 1.0.1" in (blocked.stdout + blocked.stderr)
    assert _read_version(work) == "1.0.1"

    # A single bump commit was created on top of the payload commit.
    subjects = _git(work, "log", "--format=%s", "-2").stdout.split("\n")
    assert "bump version to 1.0.1" in subjects[0]

    # Second push: version now differs from the remote baseline -> allowed.
    ok = _git(work, "push", "origin", "main", check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert _remote_version(remote, work) == "1.0.1"


def test_payload_change_with_manual_bump_passes_untouched(repo_pair):
    work, remote = repo_pair
    (work / "skills" / "demo" / "SKILL.md").write_text("# demo\nedited\n")
    (work / ".claude-plugin" / "plugin.json").write_text(
        '{\n  "name": "claudecoach",\n  "version": "1.0.5"\n}\n')
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "edit skill and bump")

    before_head = _git(work, "rev-parse", "HEAD").stdout.strip()
    ok = _git(work, "push", "origin", "main", check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    # The guard added no commit of its own.
    assert _git(work, "rev-parse", "HEAD").stdout.strip() == before_head
    assert _read_version(work) == "1.0.5"


def test_non_payload_change_passes_without_bump(repo_pair):
    work, remote = repo_pair
    (work / "README.md").write_text("# readme\nmore docs\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "docs only")

    before_head = _git(work, "rev-parse", "HEAD").stdout.strip()
    ok = _git(work, "push", "origin", "main", check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert _git(work, "rev-parse", "HEAD").stdout.strip() == before_head
    assert _read_version(work) == "1.0.0"
