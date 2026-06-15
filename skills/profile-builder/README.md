# profile-builder

A Claude Code skill that reads the **current project's** past Claude Code session
transcripts and your installed capabilities, then writes an evidence-grounded
**project profile** and **user profile**. This is Phase 1 — it *builds* the
profile; recommending skills from it is a separate Phase 2.

## What it produces

Written to `~/.claude/profiles/<slug>/`:

- `project.profile.json` — what this repo is about: domains, tech stack, task
  archetypes, relevant owned capabilities, gaps.
- `user.profile.json` — how you work here: prompting/planning/verification/steering
  style, habits, owned skills/commands/agents/MCP, strengths, and gaps.
- `profile.md` — a human-readable rendering of both.

## How it works

```
prepare (Python)            inventory (Python)
discover → sample →         skills/commands/agents/MCP
condense → scrub            at repo + personal + plugin
        │                            │
        └──── Haiku per session ─────┘
              (extract observations)
                    │
              Opus synthesis ──► project.profile + user.profile + profile.md
```

- **Plumbing is deterministic** (`scripts/sessions.py`, `scripts/inventory.py`):
  locate sessions, recency-stratified seeded sampling, strip oversized tool/edit
  bodies, scrub secrets, filter slash-command/system/skill-load machinery.
- **Interpretation is entirely LLM**: a cheap **Haiku** subagent reads each sampled
  session; one **Opus** subagent synthesizes the profiles.

## Install

```sh
ln -s "$PWD/skills/profile-builder" ~/.claude/skills/profile-builder
```

Then invoke `/profile-builder` in any project, or run the scripts directly:

```sh
python skills/profile-builder/scripts/sessions.py prepare --cwd "$PWD" --recent 20 --sample 15 --seed 0
python skills/profile-builder/scripts/inventory.py "$PWD"
```

## Privacy

- **Current project only** — it does not crawl your other projects.
- **Consent gate** before reading any transcript.
- **Local secret scrubbing** (API keys, tokens, private keys, DB URLs, env
  secrets) before any text is sent to a model; raw transcripts never leave your
  machine.
- Only condensed, scrubbed text reaches the Haiku/Opus subagents.

## Notes

- Sampling is seeded, so the same data + same `--seed` selects the same sessions;
  the LLM steps are nondeterministic (stated in each profile's `disclaimer`).
- Tests: `python -m pytest skills/profile-builder/scripts/test_scripts.py`.
- Requires Python 3 (stdlib only) and `pytest` for the tests.
```
