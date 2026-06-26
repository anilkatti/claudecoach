# ClaudeCoach: interactive Apply in actions.html + two judgment fixes

**Status:** approved design, pre-plan
**Date:** 2026-06-26
**New code:** `skills/recommend-actions/scripts/actions_server.py` (localhost selection
server) and an embedded *apply-runtime* block (toggle JS/CSS, mirroring
commentable-plans' `runtime-snippet.html`).
**Changes:** `skills/recommend-actions/` (render.py, prompts/config_doctor.md,
prompts/capability_scout.md, tests), `skills/_shared/coach_theme.py` (action_card),
`skills/perform-actions/` (SKILL.md selection filter, load_actions.py count).

## Problem

Three issues, grounded against the live run at
`~/.claude/profiles/-Volumes-Sources-cadel-mono-repo/`:

1. **The coach recommends deleting the user's globally-useful personal skills.** Three
   cards — "Archive the redundant personal `karpathy-guidelines` / `frontend-design` /
   `commit-push-pr`" — all recommend archiving the **personal** copy of a personal↔repo
   or personal↔plugin duplicate. But personal-scope capabilities are *deliberately
   global*: they travel to all of the user's work, including projects outside this repo.
   Archiving the personal copy to satisfy one repo breaks the user everywhere else. The
   `frontend-design` card is doubly wrong — it quotes that the repo *already* scopes
   personal frontend-design out, so there is no live conflict to fix. Root cause: the
   "reorganize / right-size your skills" lens in `prompts/config_doctor.md` (added
   2026-06-16, *ux-and-scope-fixes* Issue 3) treats "skills scattered across
   personal/repo/plugin scopes" as archive/scope candidates without recognizing that
   personal scope is intended to be global.

2. **The coach pushes MCP when a CLI already covers the gap.** `prompts/capability_scout.md`
   says flatly *"Prefer MCP for a live-data/tool gap."* The report duly surfaced GitHub
   MCP, Docker MCP, and Context7 — when the user's sampled sessions already drive `gh`
   and `docker` by CLI. MCP servers carry an always-on tool-schema token cost and a
   running process; the CLI the user already uses should be the default, with an MCP
   recommended only when it provides something the CLI genuinely can't.

3. **The Apply affordance is dead weight.** Each card ends in
   `<details class="apply"><summary>Apply — edit_file</summary><pre>…</pre></details>`,
   which only *reveals the raw command/diff*. There is no way to act on it. The user
   wants the commentable-plans interaction: a real **Apply** button that toggles to
   **✓ Selected for application** and persists that choice so `/perform-actions` can
   read it.

## Decisions (resolved with the user)

- **Apply flow — pre-select, still confirm each.** Clicking *Apply* marks the card
  `selected`. `/perform-actions` then walks **only the selected actions** but still asks
  yes/no on each one (today's per-action consent is preserved). Selection *filters the
  queue*; it does not auto-apply.
- **This report — fix prompts, then regenerate.** After the two prompt fixes land,
  re-run `/recommend-actions` for cadel-mono-repo so the report reflects the better
  judgment (and is rendered with the new interactive Apply UI).
- **Persistence — localhost server writing actions.json (commentable-plans pattern).**
  A small `actions_server.py` (hardened copy of `plan_server.py`) serves the profile dir;
  clicking *Apply* POSTs a toggle and the server flips `apply.status` in **actions.json**.
  actions.json stays the single source of truth; nothing downstream parses HTML.

## Architecture: the selection round-trip

```
  /recommend-actions ──renders──▶ actions.html ───opened via───▶ actions_server.py
       writes actions.json         (Apply buttons)   http://127.0.0.1:<port>/actions.html
       (every status: pending)            │  click Apply                     │
                                          └──── POST {id, selected} ─────────┘
                                                 X-Actions-Select: 1
                                                        │  flip apply.status
                                                        ▼
                                                  actions.json
                                            (that action: status=selected)  ◀─ source of truth
                                                        │
                                                        ▼
                                    /perform-actions reads actions.json,
                                    walks status=="selected", confirms each,
                                    writes applied|skipped via set_status.py
```

### State model — extend the field that already exists

`apply.status` is already `pending | applied | skipped`. Add one value, **`selected`**:

```
 pending ──[Apply click]──▶ selected ──[/perform-actions: yes]──▶ applied
    ▲                          │
    └──[Apply click again]─────┘       ──[/perform-actions: no ]──▶ skipped
```

- The server owns the `pending ↔ selected` flip (a ~10-line function — it does **not**
  import perform-actions' `set_status.py`, avoiding cross-skill coupling).
- `set_status.py` is **untouched**: it still only ever writes `applied|skipped|pending`,
  which is exactly what `/perform-actions` writes after the per-action decision.
- A regenerate resets every action to `pending` (the synthesizer always emits `pending`),
  so stale selections never carry across reports.

## `actions_server.py` (NEW — recommend-actions/scripts)

A hardened variant of commentable-plans' `plan_server.py`, serving the **profile dir**
(`~/.claude/profiles/<slug>/`) over loopback. Same security posture: binds `127.0.0.1`
only, a custom-header CSRF guard, writes confined to a single known file, body size-capped.

| Route | Method | Behavior |
|---|---|---|
| `/__actions__/health` | GET | `{"root": <served dir>, "pid": …}` — lets render.py detect an already-running server for *this* profile dir before starting another. |
| `/actions.html`, static | GET | Served by `SimpleHTTPRequestHandler` from the profile dir. |
| `/__actions__/select` | POST | Requires header `X-Actions-Select: 1` (else 403). JSON body `{"id": "<action_id>", "selected": true\|false}`. Loads `<root>/actions.json`, sets that action's `apply.status` to `selected` (true) or `pending` (false), **atomic write** (`tmp`+`os.replace`), returns `{"id", "status"}` (404 if id absent). |

The server **only ever writes `<root>/actions.json`** — never a path derived from the
request (no creation, no traversal). Port auto-bumps if taken (e.g. probe 4577–4586),
mirroring plan_server.

## `render.py` change — serve and open over http

`render_html(doc)` stays a **pure string builder** (no I/O, unit-testable); it now threads
each action's `id`/`status` into its card and appends the apply-runtime block. The
behavioral change is in `main()`: after writing `actions.html`, **find or start**
`actions_server.py`
for this profile dir (probe ports, health-check the `root`), then
`webbrowser.open("http://127.0.0.1:<port>/actions.html")`. `--no-open` prints the URL
instead of opening; a `--no-server` flag (used by tests) writes the file and skips the
server entirely. The console summary gains a one-line "open via the server to select
actions" note.

## The card + the apply-runtime block

**`action_card` (coach_theme.py).** `action_card` is used **only** by recommend-actions'
`render.py` (verified), so extending it is safe. New params: `action_id`, `status`
(default `"pending"`); `apply_kind`/`apply_preview` stay. Rendering:

- Card root carries `data-action-id` and `data-status`.
- **Actionable kinds** (`apply_kind` set and not `advisory`): emit a primary
  `<button class="apply-btn">` whose initial label follows `status` — `pending`→
  "Apply", `selected`→ "✓ Selected for application" (pressed), `applied`→ "Applied ✓"
  (disabled), `skipped`→ "Skipped". The command/diff is **demoted** to a quiet
  `<details class="apply-detail"><summary>View change</summary><pre>…</pre></details>`
  beneath the button — available, no longer the headline.
- **`advisory` kind**: no button (nothing to execute); the guidance text stands alone.

**Apply-runtime block.** A constant block (JS + CSS) injected by `render.py` at the end
of `<body>`, mirroring commentable-plans' `runtime-snippet.html` (kept as a stable,
greppable unit). The JS wires each `.apply-btn` to POST `/__actions__/select` with the
toggle, then updates the button label/`data-status` from the response; a toast reports a
failed save ("selection not saved — open this report via render.py so the server is
running"). The button/selected CSS lives in this block, keeping `_shared` free of
feature-specific styling while its only caller supplies it.

## `/perform-actions` integration

- **Step 1 (load_actions.py):** add `n_selected` to the JSON summary (count of actions
  with `apply.status == "selected"`) — transparency + a deterministic test hook. The
  filtering itself stays model-driven in the walk, per the existing pattern.
- **Step 2 (SKILL.md):** walk only actions with `status == "selected"`, in
  `do_now → consider → fyi` order, still confirming each (the per-action consent stays).
  Route and record `applied`/`skipped` exactly as today.
- **Empty-selection fallback:** if no action is `selected` (e.g. an older actions.json,
  or the user ran `/perform-actions` without selecting), the skill says so and offers to
  either open `actions.html` to select, or walk **all** actions as it does today. This
  keeps the file usable and is backward-compatible.
- **Step 3 (reorganize):** unchanged beyond the upstream filter — `edit_file` ids are
  collected from the approved *selected* actions and grouped per file as today.

## Prompt fixes

**`prompts/config_doctor.md` — personal scope is deliberately global.** In the
"reorganize / right-size your skills" lens, add: a capability present in **personal**
scope is intended to apply across *all* the user's projects, including ones outside any
given repo. A personal↔repo or personal↔plugin overlap is therefore **expected, not
redundancy** — do **not** recommend archiving the personal copy to dedupe a repo/plugin
copy; doing so removes it from every other project. The one real (small) cost of a true
byte-identical duplicate is selection ambiguity + double-maintenance, so the honest output
is at most a low-priority "these are duplicated across scopes — keep them in sync," never
an `archive` of the personal copy. Reserve `archive` for genuine dead weight (e.g. an
unused copy within the *same* scope, or a capability the user confirms is obsolete). The
existing levers (`disable-model-invocation`, `skillOverrides`, scoping, `merge_sharpen`)
and the "unused = unused in sampled sessions" rail are preserved.

**`prompts/capability_scout.md` — CLI-first; MCP must earn its place.** Replace the
blanket *"Prefer MCP for a live-data/tool gap"* with: before proposing an MCP, check
`tools_and_materials` / `owned_capabilities` for an existing **CLI** that already covers
the gap (e.g. `gh`, `docker`). If one exists, it is the default — recommend an MCP **only**
when it provides something the CLI genuinely can't (structured/programmatic access the
model can't reliably parse from CLI text, or a materially tighter loop), and say so
explicitly while weighing the MCP's always-on tool-schema token cost. The URL-verification,
no-invention, dedupe, and network-consent rails are unchanged.

## Regenerate cadel-mono-repo

After the code + prompt changes land and tests pass, re-run `/recommend-actions` for
`/Volumes/Sources/cadel-mono-repo` (its own consent + optional live lookup), producing a
fresh `actions.json` + interactive `actions.html` that omits the three archive-personal
cards and the CLI-redundant MCP cards.

## Testing strategy

All tests stay LLM-free, offline, and fast (project convention); failing test first.

- **`test_render.py`:** an actionable card carries `data-action-id` and an `apply-btn`;
  an `advisory` card has **no** button; the command/diff appears inside a "View change"
  details (not as the primary affordance); the apply-runtime block is present (assert a
  stable id). `render_html` is exercised directly (no server).
- **New `test_actions_server.py`:** POST `/__actions__/select` flips `apply.status` in a
  temp actions.json (`selected` and back to `pending`); missing `X-Actions-Select` → 403;
  unknown id → 404; a POST whose path resolves outside the served `actions.json` writes
  nothing; `/__actions__/health` returns the served root.
- **`test_coach_theme.py`:** `action_card` with the new params emits the button + data
  attributes for actionable kinds and omits it for `advisory`.
- **`test_prompts.py` (recommend-actions):** config_doctor states personal scope is
  global and warns against archiving the personal copy of a cross-scope duplicate;
  capability_scout has CLI-first guidance (mentions an existing CLI / weighs MCP token
  cost) and no longer carries the unqualified "prefer MCP" line.
- **perform-actions (`test_load_actions.py`):** `n_selected` counts only `selected`
  actions; the empty-selection case reports zero.
- `python -m pytest skills/` green before and after.

## Sequencing

1. **Prompt fixes** (config_doctor, capability_scout) + their `test_prompts` assertions —
   independent of everything else; can land first.
2. **`actions_server.py`** + `test_actions_server.py` (hardening mirrors plan_server).
3. **`action_card` + apply-runtime block** (`coach_theme.py`, `test_coach_theme.py`).
4. **`render.py`** serve/open wiring + `test_render.py` (depends on 2 and 3).
5. **`/perform-actions`** filter (`load_actions.py` `n_selected`, SKILL.md walk + fallback).
6. **Regenerate** cadel-mono-repo (runtime step, after tests are green).

## Out of scope / non-goals

- No auto-apply: selection never bypasses the per-action confirmation in `/perform-actions`.
- No "all projects together" cross-project work; no curated capabilities catalog.
- No change to what profile-builder *collects*; the only schema change is the additional
  `selected` value in `apply.status` (additive, backward-compatible).
- The File System Access API fallback (Approach B) is not built; opening `actions.html`
  as a bare `file://` shows the buttons but reports "not saved" until served — acceptable,
  since render.py always opens via the server.

## Invariants preserved

Sensor → coach → executor separation (the server is plumbing that writes data the coach
produced; it makes no judgments); opt-in / reversible apply (per-action consent unchanged;
removals still reversible archives); evidence-verified verbatim quotes; audience-neutral
language; "Models interpret; Python plumbs"; scripts run from each skill's own base
directory.
