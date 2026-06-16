"""Fixtures for the ClaudeCoach plugin-install e2e tests.

Each test drives the real `claude plugin` CLI against a throwaway
`CLAUDE_CONFIG_DIR`, so installs never touch the user's real `~/.claude`. Unlike
a `claude -p` install these are deterministic CLI calls — no model, no tokens,
no network except the one test that installs from public GitHub.

Env knobs:
  CLAUDE_PLUGIN_TEST_TIMEOUT  per-command timeout in seconds (default: 180)
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Make `import helpers` resolve regardless of pytest's import mode / cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

PLUGIN_TIMEOUT = int(os.environ.get("CLAUDE_PLUGIN_TEST_TIMEOUT", "180"))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "network: makes a real network call to github.com")


@pytest.fixture(scope="session")
def claude_bin() -> str:
    path = shutil.which("claude")
    if not path:
        pytest.skip("`claude` CLI not found on PATH; plugin e2e tests need it.")
    return path


@pytest.fixture
def isolated_config(tmp_path: Path) -> Path:
    """A throwaway CLAUDE_CONFIG_DIR so installs never touch the real ~/.claude."""
    cfg = tmp_path / "claude-config"
    cfg.mkdir()
    return cfg


@pytest.fixture
def plugin_cli(claude_bin, isolated_config):
    """Run `claude plugin <args>` against the isolated config dir.

    Returns `_run(*args, check=True) -> CompletedProcess`; raises with captured
    output on a non-zero exit when `check`. `GIT_TERMINAL_PROMPT=0` makes an
    auth-required clone fail fast instead of hanging on a credential prompt.
    """
    def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
        env = {
            **os.environ,
            "CLAUDE_CONFIG_DIR": str(isolated_config),
            "GIT_TERMINAL_PROMPT": "0",
        }
        result = subprocess.run(
            [claude_bin, "plugin", *args],
            env=env, timeout=PLUGIN_TIMEOUT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if check and result.returncode != 0:
            raise AssertionError(
                f"`claude plugin {' '.join(args)}` exited {result.returncode}\n"
                f"--- stdout ---\n{result.stdout}\n"
                f"--- stderr ---\n{result.stderr}"
            )
        return result
    return _run
