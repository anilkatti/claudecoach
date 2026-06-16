# ClaudeCoach: UX consistency & scope fixes

**Status:** approved design, pre-plan
**Date:** 2026-06-16
**New code:** `skills/_shared/coach_theme.py` (shared HTML/theme module)
**Changes:** `skills/profile-builder/` (visualize.py, SKILL.md, small sessions.py guard),
`skills/recommend-actions/` (render.py + three prompt briefs)

## Problem

Five issues were raised against the live ClaudeCoach outputs (grounded against a
real run at `~/.claude/profiles/-Volumes-Sources-cadel-mono-repo/`):

1. **Worktree scope is confusing.** The user was asked to choose between "main
   repo" and "current worktree." That prompt exists nowhere in the code — it was
   improvised at runtime. `sessions.py:discover()` already auto-merges every
   git worktree of a repo. The real ask: stop making worktrees a user decision,
   and offer the meaningful axis instead — **"this project" vs "all projects
   together."**
2. **`profile.html` surfaces truncation artifacts as evidence.** Real examples in
   the generated file: a "factual-claim discipline" strength backed by the quote
   `**There's no ` and a gap backed by `So `. Root cause confirmed:
   `visualize.py:_quote()` splits an evidence string on `"` and returns
   `parts[1]`, so any quote containing an embedded `"` is cut at the first inner
   quote. The "Your Claude setup" section is also a raw dump (`+41 more`).
3. **Recommendations under-cover skill cleanup & installs.** The coach *does*
   already emit some (3 duplicate-archives + 1 gap-scoped Promptfoo install in the
   sample), but all three `do_now` items are `capture_context`, so install/cleanup
   actions are buried in `consider`/`fyi`, and both lanes are narrow (cleanup =
   exact-duplicate dedup only; install = one gap-scoped find).
4. **No consistent UX.** `profile.html` is polished (warm paper, Fraunces/Spline
   Sans, cards, reveal animation); `actions.html` is a utilitarian dark page in
   system fonts. They share zero code — `render.py:3` even claims to "echo"
   `visualize.py` but does not.
5. **`actions.html` has no review framing.** Its only header is
   `<h1>What would make Claude work better here</h1>`. Nothing tells the user these
   are *candidate* actions to review, and that `/perform-actions` is the next step
   that walks through them.

## Decisions

Resolved with the user before design:

- **Issue 1 — fix framing, defer cross-project.** Auto-fold worktrees into "this
  project" and never ask about them. Present "this project" vs "all projects
  together," with "all projects together" marked *coming soon* (no pipeline built
  for it now).
- **Issue 3 — broaden live scout + add a reorg lens.** Keep the hard
  URL-verification gate; do not add a curated catalog.
- **Issue 4 — one shared theme module** both renderers import (single source of
  truth), unifying on the polished `profile.html` aesthetic.

## Architecture: a shared theme module

Issues 2, 4, and 5 all reduce to "how the HTML is built," so the backbone is one
shared module. Issues 1 and 3 are independent prompt/SKILL.md edits.

```
                     skills/_shared/coach_theme.py   (NEW — single source of truth)
                     ├─ esc()                         (replaces the two _esc copies)
                     ├─ TOKENS + base <style>         (warm/serif palette, lifted from
                     │                                 visualize.py's _TEMPLATE)
                     ├─ render_page(title, hero,       (full <html> scaffold:
                     │   intro, sections, footer)       head+fonts+style, .wrap, footer)
                     └─ components:
                          section()  card()  chips()  evidence()
                          callout()  stat_grid()  weighted_tags()
                               │                              │
            ┌───────────────────┘                            └───────────────────┐
            ▼                                                                      ▼
  profile-builder/scripts/visualize.py                  recommend-actions/scripts/render.py
  (extract its existing aesthetic into                  (drop the bespoke dark theme; adopt
   the shared components; keep its 4                     the shared one; keep family colors
   sections + setup-section polish)                      as card accents; add review banner)
```

**Import seam.** Each renderer's script dir is `sys.path[0]` at run time (the repo
already relies on this for sibling imports — see `context_health.py:21`). To reach
the shared module, each renderer prepends the shared dir:

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_shared"))
import coach_theme
```

The whole repo ships as the plugin (`marketplace.json` → `source: "./"`), so
`skills/_shared/` ships with it. **Open item to verify in the plan:** confirm the
plugin loader ignores a `skills/` subdirectory that has no `SKILL.md` (the leading
underscore signals "not a skill"). If it does not, fall back to a top-level
`shared/` dir (`../../../shared` from the script). This is the one packaging risk;
everything else is local refactor.

**Aesthetic.** The shared base is the warm/light `profile.html` palette
(`--paper #f5f0e8`, `--ink`, `--accent #c4562f`, `--accent2 #4d7359`, Fraunces +
Spline Sans). `actions.html`'s four action-family colors
(acquire `#7aa2f7`, config `#e3b341`, author `#bb9af7`, behavior `#7ee787`) are
preserved as a left-border accent on the shared `card()` component, so family is
still readable at a glance.

**Non-goal for now:** `perform-actions` produces no HTML report today. The shared
module is plugin-wide so a future perform-actions summary can adopt it, but we
build no perform-actions output in this effort.

## Issue 1 — scope framing (profile-builder/SKILL.md; no pipeline change)

`discover()` already folds worktrees, so this is wording + transparency, not new
collection code.

- **Step 0** states the scope plainly: *"I'll profile **this project**,
  automatically including its git worktrees."* Add an explicit instruction:
  **do not ask the user to choose between the repo and a worktree** — fold them and
  move on. After `discover()`, report which worktree roots were folded in
  (`report["worktrees"]` already carries them) so it is transparent, not silent.
- Present **"all projects together"** as a known, *coming-soon* option. If the user
  asks for it, explain it isn't available yet and offer to proceed with "this
  project." No `--scope all` pipeline, output-dir, or synthesis change now.

## Issue 2 — truthful evidence in profile.html (visualize.py + a sessions.py guard)

1. **Fix `_quote()` (the confirmed bug).** Evidence strings are
   `session:<id> "<quote>"` and the quote may contain inner `"`. Replace the
   `split('"')[1]` logic with **first-quote-to-last-quote** extraction:
   take the substring between the first `"` and the last `"` when at least two are
   present; otherwise return the string unchanged (context_health evidence such as
   `... frontend-design [personal, plugin]` has no quotes and must pass through).
   TDD: add failing cases for embedded-quote and no-quote strings first.
2. **Guard against junk quotes.** In `_evidence()` / `_quote()`, skip an evidence
   item whose *extracted* quote is empty, whitespace-only, under ~3 chars, or
   contains the truncation marker substring `profile-builder truncated`, and fall
   back to the next evidence item (up to the existing `limit`). This kills both the
   `So ` fragments (post-parse-fix safety net) and any leaked
   `[…profile-builder truncated N chars…]` marker.
3. **Polish "Your Claude setup."** The current raw dump
   (`53 capabilities never used here`, `Owned but unused here: … +41 more`) becomes,
   via the shared components: a tidy duplicates list, and an unused-capabilities
   summary (count + a bounded, collapsible list rather than a `+N more` tail). No
   change to what `context_health` *collects* — only how `_context_health()` renders
   it.

## Issue 3 — broaden recommendations (recommend-actions prompt briefs)

No schema change. Cleanup actions keep riding existing `action_type`
(`trim`/`merge_sharpen`) + `apply.kind: archive`; installs keep
`install_skill | add_mcp | add_plugin`.

- **`prompts/capability_scout.md`** — broaden the brief: in addition to narrow
  gap-scoped finds, proactively surface well-known, highly-relevant skills / MCP /
  plugins for the user's `work_type` / `domains` / `task_archetypes` that they do
  not already own. **The hard rails stay:** every recommendation needs a
  WebFetch-verified `url`; no invented names; dedupe against `owned_capabilities`;
  still gated on network consent (offline → emits `[]`).
- **`prompts/config_doctor.md`** — add an explicit **"reorganize / clean up your
  skills"** lens beyond exact-duplicate dedup: consolidate duplicates across
  personal/repo/plugin scopes, prune genuinely-unused capabilities, flag overlapping
  capabilities, and call out scope-placement problems — all as reversible `archive`
  actions. Keep the "unused = unused in sampled sessions" honesty rail.
- **`prompts/action_synthesizer.md`** — fix prioritization so one family cannot
  monopolize `do_now`. High-impact `acquire` (install) and skill-reorg actions must
  be eligible for `do_now` and not be reflexively demoted below `capture_context`.
  This directly addresses the "every action is tactical" perception.
- Update `scripts/test_prompts.py` to assert the new invariants are present in the
  briefs (structural, LLM-free).

## Issue 5 — review banner in actions.html (render.py via shared `callout()`)

A prominent banner at the top of `actions.html` (and an equivalent line in the
console output), rendered with the shared `callout()` component:

> **These are potential actions for you to review — nothing has been changed yet.**
> Next, run `/perform-actions`; Claude will walk you through each one so you can
> pick and choose which to apply.

TDD: `test_render.py` asserts the banner copy and the `/perform-actions` reference
appear in both HTML and console output.

## Testing strategy

All tests stay LLM-free, offline, and fast (project convention).

- **New** `skills/_shared/` test (e.g. `test_coach_theme.py`): `esc()` behavior,
  `render_page()` emits a well-formed doc with the shared tokens, each component
  renders expected structure.
- **`test_visualize.py`:** add embedded-quote / no-quote / junk-quote cases for
  `_quote()`+`_evidence()`; assert the page uses the shared tokens; assert the
  setup section no longer emits a `+N more` raw tail.
- **`test_render.py`:** assert shared tokens are used, the review banner +
  `/perform-actions` reference are present, and family accent colors survive.
- **`test_prompts.py` (recommend-actions):** assert the broadened scout brief,
  the reorg lens, and the prioritization rule are present.
- `python -m pytest skills/` is green before and after (goal-driven: each issue has
  a failing test first, then the fix).

## Sequencing

1. **Shared module first** — `coach_theme.py` + its tests; verify the import seam
   and the packaging open-item.
2. **Refactor `visualize.py`** onto it, folding in the issue-2 quote fix + setup
   polish.
3. **Refactor `render.py`** onto it, folding in the issue-5 banner.
4. **Prompt edits (issues 1 & 3)** — independent of the module; can land in
   parallel with steps 1–3.

## Out of scope / non-goals

- Building "all projects together" cross-project profiling (deferred; only the
  framing changes now).
- A curated capabilities catalog (decided against; live scout stays the source).
- Any `perform-actions` HTML report.
- The `actions.json` (13:47) vs `actions.html` (12:29) staleness observed in the
  sample is a re-render-ordering nit, not addressed here.
- No change to what profile-builder *collects* or to the actions.json schema.

## Invariants preserved

Sensor → coach → executor separation; collect-don't-judge (profile-builder);
opt-in / reversible apply (perform-actions); evidence-verified, verbatim quotes;
audience-neutral language; scripts run from each skill's own base directory.
