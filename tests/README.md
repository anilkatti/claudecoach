# tests

End-to-end install tests for the **ClaudeCoach plugin**. Each test drives the real
`claude plugin` CLI to install the plugin into a throwaway config dir, then asserts
the plugin lands enabled with all three skills discovered.

Unlike a `claude -p` skill install, the plugin flow is **deterministic CLI
plumbing** — no model calls, so these tests are LLM-free, fast, and free (matching
this repo's "keep tests LLM-free where possible" convention). The only network use
is the one test that installs from public GitHub.

## What each test does

`conftest.py` gives every test an isolated `CLAUDE_CONFIG_DIR` (a fresh `tmp_path`),
so nothing touches the user's real `~/.claude`. `plugin_cli` runs
`claude plugin <args>` against that dir.

| Test | What it proves | Network |
|------|----------------|---------|
| `test_plugin_manifest.py::test_manifest_validates_strict` | `.claude-plugin/{plugin,marketplace}.json` pass `claude plugin validate --strict` | no |
| `…::test_marketplace_declares_the_plugin` | the marketplace lists the plugin by name | no |
| `…::test_repo_ships_three_known_skills` | the repo ships exactly profile-builder / recommend-actions / perform-actions | no |
| `test_install_plugin.py::test_install_from_local_path` | the package is installable; all 3 skills land enabled | no |
| `…::test_install_from_public_github` | `github.com/<slug>` is pushed, public, and installs end-to-end over HTTPS | **yes** |

The two install tests share assertions: install from a source (local repo path /
HTTPS GitHub URL), then check the on-disk `skills/` of the installed plugin equals
the skills the repo ships. The GitHub test **skips** if there's no network but
**fails** on HTTP 404 — a 404 is the "not pushed / not public" case it exists to
catch.

Names, the marketplace id, and the GitHub slug are all read from the manifests
(`helpers.py`), so renaming the plugin or adding a skill doesn't silently bit-rot
the tests.

## Prerequisites

- An authenticated `claude` CLI on `PATH` (tests skip with a clear message if missing).
- `git` on `PATH`.
- `pip install -r tests/requirements.txt`

## Running

```bash
pytest tests/                      # everything (one test hits GitHub)
pytest tests/ -m "not network"     # offline only — manifest + local-path install
pytest tests/test_install_plugin.py -s   # stream the install output
```

## Env knobs

| Var | Effect |
|-----|--------|
| `CLAUDE_PLUGIN_TEST_TIMEOUT` | per-`claude plugin` command timeout, seconds (default: `180`) |

## End-user install (what these tests verify)

```
/plugin marketplace add https://github.com/anilkatti/claudecoach.git
/plugin install claudecoach@claudecoach
```

The bare `anilkatti/claudecoach` shorthand also works but clones via SSH (needs a
GitHub SSH key); the HTTPS URL above needs none.
