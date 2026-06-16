# ClaudeCoach

A Claude Code **plugin that coaches you on how you use Claude**. It first
understands you and your project, then uses that to help you get more out of
Claude. The audience is **everyone** — engineers, analysts, accountants, writers,
lawyers — so everything here is *audience-neutral*: "work" means any artifact
(a spreadsheet, a document, a dataset), never just code.

## Vision

ClaudeCoach does four things, in order of maturity:

1. **Sense** — build an evidence-verified profile of the user + project from their
   own Claude Code session history, installed capabilities, and config surface.
   *(built: `/profile-builder`)*
2. **Recommend** — which skills / MCP servers / plugins / GitHub agents to install,
   plus config and habit changes. *(built: `/recommend-actions`)*
3. **Reorganize / act** — apply the recommendations: install capabilities, trim
   config bloat, capture recurring context, and coherently rewrite CLAUDE.md/memory
   — each change reversible and opt-in. *(built: `/perform-actions`)*
4. **Monitor** *(future phase)* — watch sessions live to coach better Claude usage.

Everything runs **locally and privately** — sessions are read on-machine,
secrets scrubbed before any model sees them, and nothing is uploaded.

## Architecture: sensor → coach → executor

The product splits cleanly into a **sensor that collects, a coach that judges, and
an executor that acts**. Keep that separation — the sensor never recommends, the
coach reads only what the sensor wrote and never mutates files, and the executor only
applies what the coach proposed and the user approved.

```
  past sessions ─┐
  capabilities  ─┤   /profile-builder  (SENSOR: collect, don't judge)
  config health ─┘        │  Haiku per session · Opus synthesis
                          ▼
              ~/.claude/profiles/<slug>/{project,user}.profile.json + profile.md
                          │
                          ▼
              /recommend-actions  (COACH: judge, recommend — never mutate)
                   5 Opus subagents (4 blind specialists + 1 synthesizer)
                          │
                          ▼
              actions.html + actions.json  (prioritized, evidence-cited, opt-in)
                          │
                          ▼
              /perform-actions  (EXECUTOR: apply, don't decide)
                   a doer agent per apply.kind · per-action consent · reversible
                          │
                          ▼
              applied changes (installs · reversible archives · CLAUDE.md/memory rewrites)
```

**Models interpret; Python plumbs.** The Python scripts only do deterministic
plumbing (find, sample, condense, scrub, count, verify, render, apply). All
judgment — narratives, scoring, recommendations — is done by models. Don't push
interpretation into Python or plumbing into a prompt.

## Repo layout

- **`skills/`** — **production work. This is the real codebase.**
  - `profile-builder/` — Phase 1, the sensor.
  - `recommend-actions/` — Phase 2, the coach.
  - `perform-actions/` — Phase 3, the executor: applies approved actions via a doer
    agent per `apply.kind`; owns the reversible file primitives (`apply.py`) and the
    coherent-per-file context-reorganizer.
- **`docs/superpowers/`** — design specs (`specs/`) and implementation plans
  (`plans/`) for production skills. Write the spec/plan before building.
- **`hackathon/`** — **throwaway prototypes. Prior art / ideas, NOT a code
  dependency.** Includes `coach/` (a session-scoring coach prototype) and
  `island/` (a Tauri mac-app experiment). New work is **built fresh for
  production** in `skills/`; only lift a file from `hackathon/` if it is already
  production-grade. Don't treat `hackathon/coach/` as a foundation.

## Design invariants

These hold across every production skill — preserve them when editing:

- **Consent gate before any read.** Tell the user exactly what will be read
  (this project's transcripts, their capability inventory, their config) and wait
  for a yes before touching session data.
- **Collect, don't judge** (profile-builder). `gaps`, `friction_signals`,
  `context_health` are candidate signals *with evidence* — never verdicts.
- **Opt-in apply** (perform-actions). The coach **changes nothing**; applying is a
  separate, explicitly-consented skill — per-action, and reversible (archive not
  delete; backup before edit; diff shown first). Live web lookups in recommend-actions
  are also opt-in — declining keeps the run fully offline.
- **Evidence-verified.** Claims are backed by verbatim, verified quotes from the
  source, not paraphrase or recall.
- **Audience-neutral.** Never assume the user writes code. Treat all artifacts as
  first-class.
- **Run scripts from the skill's own base directory**; pass the user's project as
  `--cwd` / the first arg.

## Working conventions

- **TDD with pytest.** Well-tested code is non-negotiable here — failing test
  first, then implementation. Keep tests LLM-free where possible (structural /
  plumbing tests, integration smoke tests) so the suite runs offline and fast.
- **Plan → build → review.** For non-trivial work, write the spec/plan in
  `docs/superpowers/` first and get it agreed before editing code.
- **The global [Karpathy Guidelines](~/.claude/CLAUDE.md) apply** (simplicity
  first, surgical changes, minimal diff, verify before claiming done). They are
  not duplicated here — follow them.
- **Concise, concrete, sourced.** When answering questions about Claude Code /
  Anthropic capabilities, cite the docs rather than answering from memory.
- **Use ASCII diagrams** for pipelines and data flow (this repo's docs already do
  — see `hackathon/README.md`). Update nearby diagrams when you change the flow.

## Git workflow

- **Secret-scanning push protection is ON** for this repo and blocks secret-shaped
  literals — even in test fixtures. Never commit a contiguous token; split it so no
  full token appears in source (e.g. `"xoxb-" + "1111111111-abcdefghijklmnop"`). If
  a blocked literal is already in unpushed commits, purge it from history before
  pushing rather than using the allow-secret URL.
- **Commit/push only when asked.** Don't push unless the user says so.
