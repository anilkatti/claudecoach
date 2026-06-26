# profile-builder

The **sensor** for a Claude coach. It reads the **current project's** past Claude
Code session transcripts, your installed capabilities, and your config surface,
then writes an evidence-verified **project profile** and **user profile**. This is
Phase 1 — it *builds* the signals; recommending/organizing from them is a separate
downstream skill (it **collects, it does not judge**).

Works for **any profession**, not just developers — spreadsheets, documents, and
datasets count as work, the same as code.

## What it produces

Written to `~/.claude/profiles/<slug>/`:

- `project.profile.json` — what this project is: `work_type`, domains,
  tools/materials, task archetypes, relevant owned capabilities, candidate gaps.
- `user.profile.json` — how you work here: prompting/planning/verification/
  steering/leverage, friction signals, owned capabilities, **`context_health`**
  (config-bloat/contradiction signals), strengths, and candidate gaps.
- `profile.md` — a human-readable rendering of both.

## How it works

```
prepare (Python)         inventory (Python)        context_health (Python)
discover → sample →      skills/commands/           sizes · hooks · duplicate ·
condense → scrub →       agents/MCP at repo +       overlapping · unused ·
neutral + friction       personal + plugin          MCP footprint
facts                            │                          │
        │                        │                          │
        └─ Haiku per session ────┘                          │
           (work_type, friction/outcome,                    │
            leverage, verbatim evidence)                     │
                    │                                        │
            verify quotes (Python) ◀── drop fabricated ──────┘
                    │                  citations
              Opus synthesis ──► project.profile + user.profile + profile.md
```

- **Plumbing is deterministic** (`scripts/sessions.py`, `inventory.py`,
  `context_health.py`): locate sessions (across all worktrees, including removed
  ones), time-stratified seeded sampling, strip oversized bodies, scrub secrets,
  count neutral/friction facts, probe config health, and **verify every evidence
  quote** against the transcripts.
- **Interpretation is entirely LLM**: a cheap **Haiku** subagent reads each
  sampled session; one **Opus** subagent synthesizes the profiles, citing only
  quotes the verifier confirmed.

## Install

```sh
ln -s "$PWD/skills/profile-builder" ~/.claude/skills/profile-builder
```

Then invoke `/profile-builder` in any project, or run the scripts directly:

```sh
python skills/profile-builder/scripts/sessions.py prepare --cwd "$PWD" --recent 20 --sample 15 --seed 0
python skills/profile-builder/scripts/inventory.py "$PWD"
python skills/profile-builder/scripts/context_health.py "$PWD"
```

## Privacy

- **Current project only** — it does not crawl your other projects.
- **Consent gate** before reading any transcript.
- **Local secret scrubbing** (API keys, tokens, private keys, DB URLs, env
  secrets) before any text is sent to a model; raw transcripts never leave your
  machine.
- Only condensed, scrubbed text and verbatim-verified quotes reach the
  Haiku/Opus subagents.

## Notes

- Sampling's tail is seeded; the recent set is mtime-based, so re-running after
  using the project re-selects. LLM steps are nondeterministic (each profile's
  `disclaimer` says so). See `reference/limitations.md` for the full coverage register.
- **Trivial single-prompt sessions are skipped.** A lone prompt that produced no
  durable work (no files written, no commits) reveals little about how someone
  works, so selection backfills past it to fill the sample with substantive
  sessions; a one-shot run that *did* produce artifacts is kept. The count shows
  as `trivial_skipped` in the report.
- **Re-running** a project that already has a profile asks whether to overwrite
  (fresh) or update (refresh, reconciling against the existing profile).
- `context_health` and `gaps` are **signals for a downstream coach**, not
  recommendations from this skill.
- Tests: `python -m pytest skills/profile-builder/scripts/`.
- Requires Python 3 (stdlib only) and `pytest` for the tests.
