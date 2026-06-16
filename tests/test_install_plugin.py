"""Live e2e: `claude plugin` installs the ClaudeCoach plugin and all 3 skills.

Two sources, same assertions:
  - local repo path  -> offline; proves the package itself is installable.
  - public GitHub URL -> proves the repo is pushed, public, and installable by a
    real end user (HTTPS clone, no SSH key needed).

Each test installs into an isolated CLAUDE_CONFIG_DIR (see conftest) and asserts
the plugin lands enabled with every shipped skill discovered on disk.
"""
import urllib.error
import urllib.request

import pytest

import helpers


def _assert_all_skills_installed(install_path):
    got = helpers.installed_skill_names(install_path)
    want = helpers.expected_skill_names()
    assert got == want, f"installed skills {got} != shipped skills {want}"


def test_install_from_local_path(plugin_cli):
    """Offline: install straight from the repo working tree."""
    install_path = helpers.install_from(plugin_cli, str(helpers.REPO_ROOT))
    _assert_all_skills_installed(install_path)


@pytest.mark.network
def test_install_from_public_github(plugin_cli):
    """Confirms github.com/<slug> is pushed, public, and installs end-to-end."""
    _require_repo_public()
    install_path = helpers.install_from(plugin_cli, helpers.GITHUB_HTTPS_URL)
    _assert_all_skills_installed(install_path)


def _require_repo_public() -> None:
    """Skip if there's no network; FAIL (don't skip) if the repo isn't public.

    A 404 means the repo is missing or private — exactly the "is it pushed and
    public?" failure this test exists to catch, so it must not be masked as a skip.
    """
    try:
        with urllib.request.urlopen(helpers.GITHUB_BROWSE_URL, timeout=10) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise AssertionError(
                f"{helpers.GITHUB_SLUG} is not publicly reachable (HTTP 404) — "
                f"is it pushed and public?")
        raise
    except (urllib.error.URLError, TimeoutError, OSError):
        pytest.skip("no network access to github.com; skipping public-install test")
    assert status == 200, f"unexpected HTTP {status} for {helpers.GITHUB_BROWSE_URL}"
