#!/usr/bin/env python3
"""Pre-push guard: keep `.claude-plugin/plugin.json`'s version honest.

`claude plugin update` compares the published `version`, so a push that changes
the plugin's payload without bumping that field silently ships "1.0.0" twice and
leaves users on stale code. This guard prevents that.

Git invokes it as the `pre-push` hook, passing the ref lines on stdin:

    <local_ref> <local_sha> <remote_ref> <remote_sha>

For pushes to the publish branch only, if the outgoing commits touch plugin
payload but leave `version` unchanged, it bumps the patch, commits *just*
plugin.json, and aborts the push (exit 1) so the next `git push` carries the
bump. (A pre-push hook cannot inject its own commit into the push that triggered
it, so "bump + abort + push again" is the reliable shape.) Otherwise it exits 0
and the push proceeds.

This is deterministic plumbing — find, diff, compare, increment. No model.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

# The branch end users install from — only pushes here gate a version bump.
PUBLISH_BRANCH = "main"
PLUGIN_JSON = ".claude-plugin/plugin.json"
# Directories whose changes constitute a new installable version, i.e. the
# standard Claude Code plugin payload. Docs/tests/hackathon are deliberately out.
PAYLOAD_PATHS = [".claude-plugin", "skills", "commands", "agents", "hooks"]


# --- pure helpers (unit-tested) ------------------------------------------- #

def is_zero(sha: str) -> bool:
    """True for git's all-zero sha (a deletion source or a brand-new ref)."""
    return sha == "" or set(sha) <= {"0"}


def bump_patch(version: str) -> str:
    """`MAJOR.MINOR.PATCH` -> same with PATCH + 1. Raises on any other shape."""
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version.strip())
    if not m:
        raise ValueError(f"version not in MAJOR.MINOR.PATCH form: {version!r}")
    major, minor, patch = (int(g) for g in m.groups())
    return f"{major}.{minor}.{patch + 1}"


def version_from_json_text(text: str) -> str:
    return json.loads(text)["version"]


def set_version_in_json_text(text: str, new_version: str) -> str:
    """Rewrite only the version value, leaving the rest of the file byte-for-byte.

    A targeted substitution (not load/dump) keeps the commit diff to one line and
    preserves the manifest's hand-maintained formatting.
    """
    new_text, n = re.subn(
        r'("version"\s*:\s*")[^"]*(")',
        lambda m: m.group(1) + new_version + m.group(2),
        text, count=1)
    if n != 1:
        raise ValueError("expected exactly one \"version\" field to update")
    return new_text


# --- git-facing helpers ---------------------------------------------------- #

def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True).stdout


def version_at_ref(sha: str):
    """The plugin version committed at `sha`, or None if unreadable there."""
    try:
        blob = _git("show", f"{sha}:{PLUGIN_JSON}")
        return version_from_json_text(blob)
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
        return None


def payload_changed(before_sha: str, after_sha: str) -> bool:
    """Did any payload path change between the two commits? Best-effort.

    If the range can't be diffed (e.g. the remote sha isn't present locally), we
    can't judge, so we report no change and let the push through — the guard is a
    convenience, not a hard gate.
    """
    try:
        out = _git("diff", "--name-only", before_sha, after_sha, "--", *PAYLOAD_PATHS)
    except subprocess.CalledProcessError:
        return False
    return bool(out.strip())


def _abort(message: str) -> int:
    sys.stderr.write(message)
    return 1


def do_bump(pushed_sha: str) -> int:
    """Bump plugin.json's patch, commit it, and abort so it rides the next push."""
    head = _git("rev-parse", "HEAD").strip()
    if pushed_sha != head:
        # The pushed ref isn't what's checked out; committing here would land the
        # bump on the wrong branch. Make the human do it.
        return _abort(
            "\nclaudecoach pre-push: plugin payload changed but the version was not "
            f"bumped,\n  and the pushed ref ({pushed_sha[:9]}) is not your current "
            f"HEAD ({head[:9]}).\n  Bump \"version\" in {PLUGIN_JSON} manually, then "
            "push again.\n\n")

    path = Path(PLUGIN_JSON)
    text = path.read_text()
    current = version_from_json_text(text)
    new_version = bump_patch(current)
    path.write_text(set_version_in_json_text(text, new_version))
    # --no-verify so this housekeeping commit doesn't re-enter our own hooks.
    _git("commit", "--no-verify", PLUGIN_JSON,
         "-m", f"chore(plugin): bump version to {new_version}")
    return _abort(
        "\nclaudecoach pre-push: plugin payload changed but the version was not bumped.\n"
        f"  bumped {current} -> {new_version} and committed it.\n"
        "  run `git push` again to include the bump.\n\n")


def main() -> int:
    for line in sys.stdin.read().splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        _local_ref, local_sha, remote_ref, remote_sha = parts
        if is_zero(local_sha):
            continue  # deleting a remote ref — nothing to publish
        if remote_ref != f"refs/heads/{PUBLISH_BRANCH}":
            continue  # only the publish branch gates a version bump
        if is_zero(remote_sha):
            continue  # first publish of the branch — no baseline to compare
        if not payload_changed(remote_sha, local_sha):
            continue  # no installable change — no bump needed
        before, after = version_at_ref(remote_sha), version_at_ref(local_sha)
        if before is not None and after is not None and after != before:
            continue  # already bumped in this push
        return do_bump(local_sha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
