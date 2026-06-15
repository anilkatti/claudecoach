---
name: profile-builder
description: Build an evidence-verified project profile and user profile from the CURRENT project's past Claude Code sessions, the user's installed skills/commands/agents/MCP, and their config-health surface (CLAUDE.md/memory sizes, hooks, duplicate/overlapping/unused capabilities). The sensor that feeds a Claude coach. Works for ANY profession — engineer, analyst, accountant, writer, lawyer — not just developers. Use when the user wants to profile how they work in a project, understand a project's shape from its session history, audit their config for bloat/contradictions, or prepare inputs for skill recommendations. Trigger on "/profile-builder", "build my profile", "profile this project", "analyze my sessions".
---

# profile-builder

The **sensor** for a Claude coach: it reads the **current project's** session
history + the user's owned capabilities + their config surface, and writes
evidence-verified signals other skills turn into recommendations. It builds two
artifacts in `~/.claude/profiles/<slug>/`: `project.profile.json`,
`user.profile.json`, `profile.md`.

It **collects signals; it does not judge or recommend** — `gaps`,
`friction_signals`, and `context_health` are candidate signals with evidence, for
a downstream coach to act on. It works for **any kind of work**: treat
spreadsheets, documents, and datasets as first-class artifacts, never assume code.

Interpretation is done by models: **Haiku per session**, **Opus for synthesis**.
The Python scripts only do plumbing (find, sample, condense, scrub, count,
verify). Run the scripts from **this skill's own directory** (the base directory
shown when the skill loads); pass the user's project as `--cwd` / the first arg.

## Step 0 — Consent gate (required, before any read)
Tell the user, and wait for a yes:
> "I'll read THIS project's Claude Code session transcripts (a recency-stratified
> sample) and inventory your installed skills/commands/agents/MCP plus your
> config surface (CLAUDE.md & memory sizes, hooks, duplicate/unused capabilities).
> Secrets are scrubbed locally and slash-command/system machinery is stripped;
> only condensed, scrubbed text and verbatim-verified quotes reach the
> Haiku/Opus subagents. Proceed?"

## Step 1 — Prepare sessions (plumbing)
Run: `python scripts/sessions.py prepare --cwd "<project cwd>" --recent 20 --sample 15 --seed 0`
Parse the stdout JSON: `{slug, report, sessions[]}`. Show the `report` to the user
(totals / sampled / skipped / too_short / truncated) — never hide truncation.

## Step 2 — Inventory (plumbing)
Run: `python scripts/inventory.py "<project cwd>"` → `owned_capabilities` JSON.

## Step 3 — Per-session extraction (Haiku subagents)
For each session in `sessions[]` where `too_short` is `false`:
- Dispatch a subagent with **model: haiku** using `prompts/per_session_extract.md`,
  substituting `{{SESSION_ID}}` and `{{CONDENSED_TEXT}}`.
- Dispatch in parallel waves of ~8–10. If the eligible count exceeds 30, batch
  ~5 sessions per subagent (concatenate them in the prompt, ask for a JSON array)
  to cap total dispatches.
- Collect each subagent's JSON. Strip any surrounding ```json fences before
  parsing (subagents add them despite instructions). If a result is still not
  valid JSON, retry that subagent once; if it still fails, drop it and increment
  `extraction_failures`.
- **Attach each session's deterministic `facts`** (from Step 1, incl.
  `artifacts`, `tool_errors`, `duration_seconds`) to its observation so synthesis
  sees friction facts, not just the LLM read.

## Step 4 — Config-health (plumbing)
Collect `used_names` = the union of every observation's
`how_they_worked.skills_invoked`. Run:
`python scripts/context_health.py "<project cwd>" <used_name> <used_name> …`
→ `context_health` JSON (always-on sizes, hooks, duplicate/overlapping/unused
capabilities, MCP footprint). Passing `used_names` makes `unused_capabilities`
accurate. This is **raw signal** — do not judge it.

## Step 5 — Verify evidence (plumbing — the evidence-contract guard)
Build `quotes` = every `evidence[].quote` across all observations, and `texts` =
every `sessions[].condensed_text`. Pipe `{"quotes": [...], "texts": [...]}` as
JSON to `python scripts/sessions.py verify` → `{verified, dropped}`. Drop any
unverified quote (and observations left with no evidence) before synthesis;
record `quotes_verified` / `quotes_dropped` in provenance. This guarantees the
profile can only cite quotes that provably appear in a transcript.

## Step 6 — Synthesis (one Opus subagent)
Dispatch a subagent with **model: opus** using `prompts/synthesize_profile.md`,
substituting `{{SLUG}}`, `{{PROVENANCE_JSON}}` (the `report` + model tiers +
`extraction_failures` + `quotes_verified`/`quotes_dropped` + `truncated_sessions`),
`{{INVENTORY_JSON}}`, `{{CONTEXT_HEALTH_JSON}}`, `{{CONTEXT}}` (contents of
`~/.claude/CLAUDE.md`, `<repo>/CLAUDE.md`, and the project memory index at
`~/.claude/projects/<slug>/memory/MEMORY.md` if present — else empty), and
`{{OBSERVATIONS_JSON}}` (the verified array from Steps 3–5). Have the subagent
read `reference/schema.md` so field names match exactly. Split its output on
`===PROJECT===` / `===USER===`, stripping any ```json fences around each block.

## Step 7 — Write outputs
Create `~/.claude/profiles/<slug>/` and write `project.profile.json`,
`user.profile.json`, and a human-readable `profile.md` rendering both (project
summary + work_type, user summary, the content areas, behavioral signals,
friction signals, strengths/gaps, a context-health section, and the
provenance/disclaimer fine print). Validate each JSON parses before writing.

## Step 8 — Summarize to the user
Print where the files were written and the headline provenance (sessions
sampled / skipped / truncated, extraction failures, quotes verified vs dropped,
model tiers). Remind them the profiles are LLM-derived and nondeterministic, that
this is the current project only (cross-project merge is a later phase), and that
`context_health`/`gaps` are signals for a coach, not recommendations from here.

## Honesty rails
- Consent before reading; secrets scrubbed before anything leaves the machine.
- Seeded sampling makes the tail reproducible, but the recent set is mtime-based,
  so re-running after using the project re-selects; the LLM steps always vary.
- No silent truncation: surface the sampling report, `truncated` sessions, and
  failure counts.
- Every profile claim cites a **verified** verbatim quote; unverifiable quotes are
  dropped, never guessed. Never invent signals.
- `context_health` and `gaps` are raw/candidate signals — this skill does not
  recommend; it senses.

## Tests
`python -m pytest scripts/` exercises the plumbing (sessions, inventory,
context-health, evidence verification).
