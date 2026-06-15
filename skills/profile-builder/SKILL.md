---
name: profile-builder
description: Build an evidence-grounded project profile and user profile from the CURRENT repo's past Claude Code sessions and the user's installed skills/commands/agents/MCP. Use when the user wants to profile how they work in a project, understand a project's shape from its session history, or prepare inputs for skill recommendations. Trigger on "/profile-builder", "build my profile", "profile this project", "analyze my sessions".
---

# profile-builder

Builds two artifacts for the **current project only** from its Claude Code
session history + the user's owned capabilities, written to
`~/.claude/profiles/<slug>/`: `project.profile.json`, `user.profile.json`,
`profile.md`.

Interpretation is done entirely by models: **Haiku per session**, **Opus for
synthesis**. The Python scripts only do plumbing (find, sample, condense, scrub).
Run the scripts from **this skill's own directory** (the base directory shown when
the skill loads); run them with the user's project as `--cwd`.

## Step 0 — Consent gate (required, before any read)
Tell the user, and wait for a yes:
> "I'll read THIS repo's Claude Code session transcripts (a recency-stratified
> sample) and inventory your installed skills/commands/agents/MCP. Secrets are
> scrubbed locally and slash-command/system machinery is stripped; only condensed,
> scrubbed text is sent to Haiku/Opus subagents. Proceed?"

## Step 1 — Prepare sessions (plumbing)
Run: `python scripts/sessions.py prepare --cwd "<project cwd>" --recent 20 --sample 15 --seed 0`
Parse the stdout JSON: `{slug, report, sessions[]}`. Show the `report` to the user
(totals / sampled / skipped / too_short) — never hide truncation.

## Step 2 — Inventory (plumbing; can run alongside Step 3)
Run: `python scripts/inventory.py "<project cwd>"` → `owned_capabilities` JSON.

## Step 3 — Per-session extraction (Haiku subagents)
For each session in `sessions[]` where `too_short` is `false`:
- Dispatch a subagent with **model: haiku** using `prompts/per_session_extract.md`,
  substituting `{{SESSION_ID}}` and `{{CONDENSED_TEXT}}`.
- Dispatch in parallel waves (≈8–10 at a time). If the eligible count > 30, batch
  ~5 sessions per subagent to cap dispatches.
- Collect each subagent's JSON. Strip any surrounding ```json code fences before
  parsing (subagents often add them despite instructions). If a result is still
  not valid JSON, retry that subagent once; if it still fails, drop it and
  increment `extraction_failures`.
- Skip `too_short` sessions; record how many were skipped.

## Step 4 — Synthesis (one Opus subagent)
Dispatch a subagent with **model: opus** using `prompts/synthesize_profile.md`,
substituting `{{SLUG}}`, `{{PROVENANCE_JSON}}` (the `report` plus model tiers and
`extraction_failures`), `{{INVENTORY_JSON}}`, `{{CONTEXT}}` (contents of
`~/.claude/CLAUDE.md`, `<repo>/CLAUDE.md`, and the repo's `MEMORY.md` if present —
else empty), and `{{OBSERVATIONS_JSON}}` (the array from Step 3). Have the subagent
read `reference/schema.md` so field names match exactly. Split its output on
`===PROJECT===` / `===USER===`, stripping any ```json fences around each block
before parsing/validating.

## Step 5 — Write outputs
Create `~/.claude/profiles/<slug>/` and write `project.profile.json`,
`user.profile.json`, and a human-readable `profile.md` rendering both (project
summary, user summary, the four content areas, strengths/gaps, and the
provenance/disclaimer fine print). Validate each JSON parses before writing.

## Step 6 — Summarize to the user
Print where the files were written and the headline provenance (sessions
sampled/skipped, extraction failures, model tiers). Remind them the profiles are
LLM-derived and nondeterministic, and that this is the current project only
(cross-project merge is a later phase).

## Honesty rails
- Consent before reading; secrets scrubbed before anything leaves the machine.
- Seeded sampling → same data + same seed picks the same sessions; LLM steps vary.
- No silent truncation: surface the sampling report and failure counts.
- Every profile claim must cite evidence; never invent signals.

## Tests
`python -m pytest scripts/test_scripts.py` exercises the plumbing.
