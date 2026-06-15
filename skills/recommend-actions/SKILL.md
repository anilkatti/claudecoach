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
> already scrubbed), match its gaps against a curated capabilities + best-practices
> index, and write a recommendations report. By default I change nothing. May I also
> do **optional live web lookups** to find newer skills and confirm sources? (yes/no —
> declining keeps the run fully offline.)"

Record `network_used` (true only if they allowed live lookups).

## Step 1 — Load the profile (plumbing)
Run: `python scripts/load_profile.py "<project cwd>"`
Parse stdout JSON. If `error == "no_profile"`: tell the user no profile exists for this
project and **offer to run `/profile-builder` first** — then stop. Otherwise keep
`slug`, `dir`, `freshness`, `sessions_sampled`, and the four `lanes`.

## Step 1.5 — Freshness
If `freshness.stale` is true (or `age_days` is null), tell the user the profile's date
and offer to re-run `/profile-builder` before recommending. Proceed only if they want to.

## Step 2 — Fan out the four specialists (parallel, model: opus)
Read `reference/capabilities_index.json` and `reference/best_practices.json`. Dispatch
**four subagents in parallel, each with model: opus**, substituting placeholders:
- `prompts/capability_scout.md` — `{{LANE_JSON}}`=lanes.acquire, `{{INDEX_JSON}}`=capabilities_index.
- `prompts/config_doctor.md` — `{{LANE_JSON}}`=lanes.config.
- `prompts/pattern_smith.md` — `{{LANE_JSON}}`=lanes.author.
- `prompts/practice_coach.md` — `{{LANE_JSON}}`=lanes.behavior, `{{INDEX_JSON}}`=best_practices.

If `network_used`, tell the two research agents (scout, coach) they may use WebSearch/
WebFetch to top-up and **verify** candidates, and must keep `source.url` accurate.

Collect each agent's JSON array. Strip any surrounding ```json fences before parsing.
If a result isn't valid JSON, retry that agent once; if it still fails, drop it and
note the dropped lane to the user. Concatenate the four arrays → `candidates`.

## Step 3 — Synthesize (one subagent, model: opus)
Dispatch `prompts/action_synthesizer.md` with model: opus, substituting:
- `{{PROFILE_JSON}}` = the project + user profiles (for evidence re-grounding),
- `{{CANDIDATES_JSON}}` = `candidates`,
- `{{META_JSON}}` = `{project_slug: slug, generated_at: <now ISO>, profile_ref:
  {generated_at, stale, sessions_sampled}, indexes: {capabilities_built_at,
  best_practices_built_at}, consent: {network_used}}` — read `capabilities_built_at` /
  `best_practices_built_at` from each index file's top-level `built_at` key.
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
sample"; research is only as fresh as the index build (+ any live top-up); habit
findings are correlational; removals were reversible.

## Honesty rails
- Read-only and non-networked by default; network and each apply are separately consented.
- Every action cites a profile signal; never recommend a capability/practice without a
  real URL; correlational (not causal) language for habits; removals reversible.

## Tests
`python -m pytest scripts/` exercises the plumbing (load, build, render, apply, prompts).
