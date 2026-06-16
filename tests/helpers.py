"""Shared helpers for the ClaudeCoach plugin-install e2e tests.

The plugin's manifests (`.claude-plugin/{plugin,marketplace}.json`) are the source
of truth: names, the marketplace id, and the GitHub slug are all read from them,
so the tests stay honest if the plugin is renamed or a skill is added/removed.

These are structural/plumbing helpers — pure functions over the manifest and over
the artifacts a `claude plugin install` leaves on disk. No model calls.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
PLUGIN_DIR = REPO_ROOT / ".claude-plugin"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


PLUGIN_MANIFEST = _read_json(PLUGIN_DIR / "plugin.json")
MARKETPLACE_MANIFEST = _read_json(PLUGIN_DIR / "marketplace.json")

PLUGIN_NAME = PLUGIN_MANIFEST["name"]
MARKETPLACE_NAME = MARKETPLACE_MANIFEST["name"]
# `claude plugin install <name>@<marketplace>` and the id reported by `plugin list`.
PLUGIN_ID = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"


def github_slug() -> str:
    """`owner/repo` parsed from the plugin manifest's repository/homepage URL."""
    url = PLUGIN_MANIFEST.get("repository") or PLUGIN_MANIFEST.get("homepage", "")
    m = re.search(r"github\.com[:/]+([^/]+/[^/.\s]+)", url)
    if not m:
        raise AssertionError(f"can't parse a github slug from manifest url: {url!r}")
    return m.group(1)


GITHUB_SLUG = github_slug()
# HTTPS clone URL needs no SSH key — the portable form for end users. (The bare
# `owner/repo` shorthand resolves to git@github.com SSH, which needs a key.)
GITHUB_HTTPS_URL = f"https://github.com/{GITHUB_SLUG}.git"
GITHUB_BROWSE_URL = f"https://github.com/{GITHUB_SLUG}"


def expected_skill_names() -> set[str]:
    """The skills the source repo ships — one `skills/<name>/SKILL.md` each."""
    return {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}


def installed_skill_names(install_path: Path) -> set[str]:
    """The skills present under an installed plugin's on-disk `skills/` dir."""
    return {p.parent.name for p in (install_path / "skills").glob("*/SKILL.md")}


def _loads_lenient(text: str):
    """`json.loads`, tolerating leading progress lines before the JSON body."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = min((i for i in (text.find("["), text.find("{")) if i != -1),
                    default=-1)
        if start == -1:
            raise
        return json.loads(text[start:])


def install_from(plugin_cli, source: str) -> Path:
    """Add `source` as a marketplace, install the plugin, return its install path.

    `plugin_cli` is the conftest fixture that runs `claude plugin ...` against an
    isolated config dir. Asserts the plugin lands enabled; returns the on-disk
    `installPath` reported by `claude plugin list --json`.
    """
    plugin_cli("marketplace", "add", source)
    plugin_cli("install", PLUGIN_ID, "--scope", "user")
    listing = _loads_lenient(plugin_cli("list", "--json").stdout)
    entry = next((p for p in listing if p["id"] == PLUGIN_ID), None)
    assert entry is not None, f"{PLUGIN_ID} not in `plugin list`: {listing}"
    assert entry["enabled"], f"{PLUGIN_ID} installed but not enabled: {entry}"
    return Path(entry["installPath"])
