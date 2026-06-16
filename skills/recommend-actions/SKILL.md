---
name: recommend-actions
description: Phase-2 coach for ClaudeCoach. Reads the profile-builder profile for THIS project and produces prioritized, evidence-cited, opt-in-apply recommendations to get more out of Claude — acquire skills/MCP/plugins, tune config (trim bloat, capture recurring context, automate steps), author a reusable asset from a recurring pattern, and adopt/stop habits per Anthropic/OpenAI best practices. Output is actions.html + actions.json. Use after /profile-builder, or when the user asks "what should I change to use Claude better", "recommend actions", "what skills should I install", "cut my context bloat". Trigger on "/recommend-actions".
---

# recommend-actions

The **judge/coach** half of ClaudeCoach. profile-builder senses (collect, don't judge);
this skill recommends. It consumes the **current project's** profile-builder v2 output
and emits an evidence-cited, opt-in-apply action set. Run scripts from **this skill's
own directory**; pass the user's project as the first arg / `--cwd`.

Interpretation is done by **five Opus subagents** (four blind specialists + one
synthesizer). Python only does plumbing (load, build indexes, render, apply primitives).

## Step 0 — Consent gate (before any read)
Tell the user and wait for a yes:
> "I'll read THIS project's profile that /profile-builder already built (local JSON,
> already scrubbed), match its signals against a best-practices index, and write a
> recommendations report. By default I change nothing. Finding new skills/MCP/plugins
> needs a **one-time live, profile-scoped web lookup** (cached per project afterward,
> so re-runs stay offline). May I do that live lookup? (yes/no — declining keeps the
> run fully offline; you'll still get config, authoring, and habit advice.)"

Record `network_used` (true only if they allowed live lookups).

## Step 1 — Load the profile (plumbing)
Run: `python scripts/load_profile.py "<project cwd>"`
Parse stdout JSON. If `error == "no_profile"`: tell the user no profile exists for this
project and **offer to run `/profile-builder` first** — then stop. Otherwise keep
`slug`, `dir`, `freshness`, `sessions_sampled`, and the four `lanes`.

## Step 1.5 — Freshness
If `freshness.stale` is true (or `age_days` is null), tell the user the profile's date
and offer to re-run `/profile-builder` before recommending. Proceed only if they want to.

## Step 2 — Fan out the specialists (parallel, model: opus)
Read `reference/best_practices.json`. Dispatch the three **non-acquire** specialists
in parallel, each **model: opus**, substituting placeholders:
- `prompts/config_doctor.md` — `{{LANE_JSON}}`=lanes.config.
- `prompts/pattern_smith.md` — `{{LANE_JSON}}`=lanes.author.
- `prompts/practice_coach.md` — `{{LANE_JSON}}`=lanes.behavior, `{{INDEX_JSON}}`=best_practices.

### Step 2a — Acquire lane (cache-aware, live)
The acquire lane is sourced live and cached per project. Take the profile's
`generated_at` from Step 1's `freshness.generated_at`, then run:
`python scripts/cache.py status "<dir>" --profile-generated-at "<generated_at>"`
Branch on its JSON:
- **`fresh: true`** → reuse the cache: read `<dir>/capabilities_cache.json` and use its
  `candidates` as the acquire candidates. No scout dispatch, no network. Set
  `capabilities_fetched_at` (for Step 3) to the cache's `fetched_at`.
- **`fresh: false`** (includes `exists: false`):
  - If `network_used` → dispatch `prompts/capability_scout.md` (**model: opus**),
    `{{LANE_JSON}}`=lanes.acquire; tell it live research is enabled and it must
    WebFetch-verify every URL. Collect its JSON array, write it to a temp file, and
    persist it: `python scripts/cache.py write "<dir>" <temp.json>
    --profile-generated-at "<generated_at>" --network-used`. Set
    `capabilities_fetched_at` to `"live"`.
  - If **not** `network_used` → if `exists: true`, reuse the stale cache's candidates
    and warn the user they may be out of date (set `capabilities_fetched_at` to the
    cache's `fetched_at`); else there are **no acquire candidates** — tell the user
    acquiring new capabilities needs a live lookup (set `capabilities_fetched_at` to
    `"none"`).

Collect each agent's JSON array. Strip any surrounding ```json fences before parsing.
If a result isn't valid JSON, retry that agent once; if it still fails, drop it and
note the dropped lane to the user. Concatenate the four lanes' arrays → `candidates`.

## Step 3 — Synthesize (one subagent, model: opus)
Dispatch `prompts/action_synthesizer.md` with model: opus, substituting:
- `{{PROFILE_JSON}}` = the project + user profiles (for evidence re-grounding),
- `{{CANDIDATES_JSON}}` = `candidates`,
- `{{META_JSON}}` = `{project_slug: slug, generated_at: <now ISO>, profile_ref:
  {generated_at, stale, sessions_sampled}, indexes: {capabilities_fetched_at: <from
  Step 2a — the cache's fetched_at, "live", or "none">, best_practices_built_at},
  consent: {network_used}}` — read `best_practices_built_at` from
  `reference/best_practices.json`'s top-level `built_at` key.
Have it read `reference/schema.md` so field names match. Parse its single JSON object
(strip fences); validate it parses and has `actions`. Write it to `<dir>/actions.json`.

## Step 4 — Render + offer to view
Run: `python scripts/render.py "<dir>/actions.json" --no-open` to print the console
summary. Then **ask** the user: "Want me to open the visual report in your browser?"
If yes, run `python scripts/render.py "<dir>/actions.json"` (opens `actions.html`).

## Step 5 — Apply loop (opt-in, per action)
Walk the actions in `do_now` → `consider` → `fyi` order. For each, show its title +
rationale + `apply.preview`, then ask whether to apply it. Only on an explicit yes:
- `run_command` → run the shown command.
- `edit_file` → show the diff (`python scripts/apply.py diff <path> <new_file>`),
  then `python scripts/apply.py edit <path> <new_file>` (backs up first).
- `archive` → remove a capability reversibly: `python scripts/apply.py archive <path> <archive_dir>`
  (moves it to an archive dir; never deletes — undo with `python scripts/apply.py restore <archived> <orig>`).
- `scaffold_skill` → invoke the `skill-creator` skill with the drafted spec.
- `handoff_skill` → invoke the named skill (`update-config` / `fewer-permission-prompts`).
- `advisory` → nothing to apply; it's guidance.
Update that action's `apply.status` to `applied`/`skipped` in `actions.json` as you go.

## Step 6 — Summarize
Tell the user where `actions.json` / `actions.html` live, what was applied vs skipped,
and the headline honesty rails: LLM-derived & nondeterministic; "unused" means "in the
sample"; capability research is only as fresh as the per-project cache (up to a 14-day TTL, or live if refreshed this run); habit
findings are correlational; removals were reversible.

## Honesty rails
- Read-only and non-networked by default; network and each apply are separately consented.
- Every action cites a profile signal; never recommend a capability/practice without a
  real URL; correlational (not causal) language for habits; removals reversible.

## Tests
`python -m pytest scripts/` exercises the plumbing (load, build, render, apply, prompts).
