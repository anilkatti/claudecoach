# ClaudeCoach

A Claude Code **plugin that coaches you on how you use Claude.** It learns who you are
and what your project is from your own session history, then helps you get more out of
Claude — what to install, what to trim, what to change — and applies the changes you
approve.

It's for **everyone** who works with Claude Code — engineers, analysts, accountants,
writers, lawyers. "Work" means any artifact: a spreadsheet, a document, a dataset, a
codebase. Nothing here assumes you write code.

Everything runs **locally and privately.** Your sessions are read on your machine,
secrets are scrubbed before any model sees them, and nothing is uploaded.

## How it works

ClaudeCoach is three skills you run in order — a **sensor** that collects, a **coach**
that judges, and an **executor** that acts. Each stays in its lane: the sensor never
recommends, the coach never senses and never touches your files, the executor only
applies what the coach proposed and you approved.

```
  your past sessions ─┐
  installed skills    ─┤  /profile-builder   ─▶  ~/.claude/profiles/<slug>/
  config health       ─┘   (SENSE)                project + user profile, profile.md
                                                          │
                                                          ▼
                          /recommend-actions   ─▶  actions.json + actions.html
                           (RECOMMEND)               prioritized, evidence-cited
                                                          │
                                                          ▼
                          /perform-actions     ─▶  applied changes
                           (DO)                      reversible, per-action consent
```

### 1. `/profile-builder` — Sense
Reads **this project's** Claude Code transcripts (a sampled, scrubbed subset), inventories
your installed skills/commands/agents/MCP servers, and measures your config surface
(CLAUDE.md & memory size, hooks, duplicate/unused capabilities). It **collects evidence,
it does not judge** — every signal is backed by a verbatim, verified quote from a real
transcript. Output: `project.profile.json`, `user.profile.json`, and a readable
`profile.md` / `profile.html` in `~/.claude/profiles/<slug>/`.

### 2. `/recommend-actions` — Recommend
Reads the profile and produces a prioritized, evidence-cited, opt-in action set across
four families: **acquire** (skills / MCP / plugins that fill a real gap, researched live
and verified), **config** (trim bloat, capture recurring context, automate a step),
**author** (turn a recurring pattern into the lightest reusable asset), and **behavior**
(adopt/stop habits, cited to Anthropic/OpenAI guidance). It **recommends; it changes
nothing.** Output: `actions.json` + a browsable `actions.html`.

### 3. `/perform-actions` — Do
Walks `actions.json` and applies the actions **you approve**, each via a doer agent for
its kind: install a capability, archive an unused one, scaffold a skill, hand off to a
config skill, or **coherently rewrite a CLAUDE.md/memory file** for capture/trim edits.
Every change is shown as a diff or command first; removals are **reversible archives**
(moved aside, never deleted) and edits are backed up. It's the only skill that touches
your files, and only on explicit per-action consent.

## Install

Install all three skills as one plugin (from inside Claude Code):

```
/plugin marketplace add anilkatti/claudecoach
/plugin install claudecoach@claudecoach
```

`/plugin marketplace add` also accepts a local path (`/plugin marketplace add /path/to/claudecoach`).
Installed this way, the skills load namespaced as `/claudecoach:profile-builder`,
`/claudecoach:recommend-actions`, and `/claudecoach:perform-actions`.

<details><summary>Dev install (symlinks instead of the plugin)</summary>

```sh
cd /path/to/claudecoach
ln -s "$PWD/skills/profile-builder"   ~/.claude/skills/profile-builder
ln -s "$PWD/skills/recommend-actions" ~/.claude/skills/recommend-actions
ln -s "$PWD/skills/perform-actions"   ~/.claude/skills/perform-actions
```
</details>

Then, in any project, run them in order: **profile-builder → recommend-actions → perform-actions.**

## Privacy

- Transcripts are read **on your machine**; secrets are scrubbed before any model sees them.
- Only condensed, scrubbed text and verbatim-verified quotes reach a model. Raw
  transcripts never leave the machine.
- Live web lookups (to find new capabilities) are **opt-in** — declining keeps the run
  fully offline.
- Nothing is applied until you approve it; every removal is reversible.

## Repo layout

- **`skills/`** — the production skills (`profile-builder`, `recommend-actions`,
  `perform-actions`). The real codebase.
- **`docs/superpowers/`** — design specs (`specs/`) and implementation plans (`plans/`);
  the spec/plan is written before each skill is built.
- **`hackathon/`** — throwaway prototypes and prior art (a session-scoring coach, a
  Tauri menubar experiment). Not a dependency.

## Design principles

- **Models interpret; Python plumbs.** Scripts only do deterministic work (sample,
  scrub, verify, group, render, apply). All judgment is done by models.
- **Evidence-verified.** Every claim cites a verbatim quote that provably appears in a
  transcript; unverifiable claims are dropped, never guessed.
- **Reversible & consented.** The coach changes nothing by default; applying is a
  separate, per-action, reversible step.

## Status

Phases 1–3 (Sense, Recommend, Do) are built and tested. Phase 4 (Monitor — live
session coaching) is future work.

## Tests

Each skill ships an offline, LLM-free test suite:

```sh
python -m pytest skills/profile-builder/scripts/
python -m pytest skills/recommend-actions/scripts/
python -m pytest skills/perform-actions/scripts/
```
