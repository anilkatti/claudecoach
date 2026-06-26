# Profile schemas (v2)

Two artifacts are written to `~/.claude/profiles/<slug>/`. Both are
**evidence-grounded and evidence-*verified***: every `domains` / `tools_and_materials`
/ `task_archetypes` / `strength` / `gap` cites a `session:<id>` and a **verbatim
quote that has been checked, deterministically, to appear in that session's
condensed transcript** (`scripts/sessions.py verify`). A quote that can't be
verified is dropped, never guessed. Phase 1 covers the **current project only**.

**Audience-neutral.** The person may be an engineer, analyst, accountant, writer,
lawyer, or any professional directing Claude. "Work" means artifacts of **any**
kind (spreadsheets, documents, datasets, code), not just code. Never assume software.

## `project.profile.json` — what this project is & what work happens in it

```json
{
  "schema_version": 2,
  "kind": "project",
  "generated_at": "<ISO8601>",
  "project": {"slug": "...", "root": "<cwd>", "git_remote": "...",
              "worktrees_merged": ["..."]},
  "work_type": "software | data-analysis | writing | research | ops | finance | design | admin | mixed | other",
  "summary": "2-3 plain-English sentences on what this project is and the work done here",
  "domains":              [{"name": "...", "weight": 0.0, "evidence": ["session:<id> \"verbatim quote\""]}],
  "tools_and_materials":  [{"name": "...", "weight": 0.0, "evidence": ["..."]}],
  "task_archetypes":      [{"name": "...", "weight": 0.0, "evidence": ["..."]}],
  "project_relevant_capabilities": [{"name": "...", "source": "repo|personal|plugin",
                                     "used_here": true}],
  "gaps": [{"need": "...", "rationale": "...", "confidence": 0.0, "evidence": ["..."]}],
  "provenance": {"...": "see shared provenance below"},
  "disclaimer": "LLM-derived from a time-stratified sample; evidence-verified but nondeterministic."
}
```

`weight` ∈ [0,1] on `domains` / `tools_and_materials` / `task_archetypes` means
**prevalence** — how much of the sampled work the entry represents (its share of
sampled sessions as a *primary* activity) — **not** how decisively a single session
proves it. Weights are independent and need not sum to 1. Because the sample is
time-stratified across the project's whole history, the bars track "what the work
mostly is," not "which session had the most quotable line."

`tools_and_materials` replaces v1's `tech_stack`: it holds code stacks **and**
non-code materials (e.g. "Excel workbooks", "court filings", "CSV exports").

## `user.profile.json` — how this person works, observed in this project only

```json
{
  "schema_version": 2,
  "kind": "user",
  "generated_at": "<ISO8601>",
  "observed_in": {"project_slug": "...",
                  "note": "behavior observed within this project only; cross-project merge deferred"},
  "summary": "2-3 plain-English sentences on how this person works",
  "working_style":      [{"preference": "...", "evidence": ["..."]}],
  "behavioral_signals": {
    "prompting":    {"value": "...", "evidence": ["..."]},
    "planning":     {"value": "...", "evidence": ["..."]},
    "verification": {"value": "...", "evidence": ["..."]},
    "steering":     {"value": "...", "evidence": ["..."]},
    "leverage":     {"value": "...", "evidence": ["..."]}
  },
  "friction_signals": [{"pattern": "...", "evidence": ["..."], "confidence": 0.0}],
  "habits": [{"label": "...", "polarity": "strength|holding-back",
              "evidence": "k of n sampled sessions", "detail": "..."}],
  "owned_capabilities": {"skills": [{"name": "...", "description": "...", "source": "..."}],
                         "commands": [], "agents": [], "mcp_servers": [{"name": "...", "source": "..."}]},
  "skill_usage": [{"name": "...", "sessions_seen": 0}],
  "context_health": { "...": "raw config signals — see below; NO recommendations" },
  "strengths": [{"area": "...", "evidence": ["..."]}],
  "gaps":      [{"area": "...", "rationale": "...", "confidence": 0.0, "evidence": ["..."]}],
  "provenance": {"...": "see shared provenance below"},
  "disclaimer": "..."
}
```

- **`leverage`** is now produced per session by the extractor, so synthesis no
  longer invents it. It means outcome-per-input: did the person's direction turn
  Claude's effort into a closed loop (a finished artifact, a resolved question)?
- **`friction_signals`** are evidence-grounded observations of where work snagged
  — repeated re-explaining of context a `CLAUDE.md`/memory could hold, rework
  loops, abandoned attempts. These are the richest hooks for a downstream coach.
- **`gaps`** carry a `confidence` and are **candidate signals, not
  recommendations** — the sensor surfaces them; a downstream skill decides.

### `context_health` — the Goal-2 signal block (collect, don't judge)

Copied verbatim from `scripts/context_health.py`. **Raw signals only — no verdicts.**

```json
{
  "always_on": {"sources": [{"scope": "global|repo|memory", "path": "...", "lines": 0, "chars": 0}],
                "total_chars": 0, "est_tokens": 0},
  "hooks": [{"event": "...", "scope": "global|global-local|repo|repo-local", "count": 0}],
  "duplicate_capabilities":   [{"name": "...", "kind": "skills|commands|agents", "sources": ["..."]}],
  "overlapping_capabilities": [{"a": "...", "b": "...", "kind": "skills", "overlap": 0.0}],
  "mcp_footprint":            {"servers": 0, "by_source": {"...": 0}},
  "unused_capabilities":      [{"name": "...", "kind": "...", "source": "..."}]
}
```

## Shared `provenance`

```json
{"sessions_total": 0, "sessions_sampled": 0, "sampling": "time-stratified",
 "seed": 0, "skipped_short": 0, "trivial_skipped": 0, "too_short_chosen": 0,
 "truncated_sessions": 0, "extraction_failures": 0,
 "quotes_verified": 0, "quotes_dropped": 0,
 "models": {"per_session": "claude-haiku-4-5-20251001", "synthesis": "claude-opus-4-8"}}
```

Selection partitions the project's whole history (all worktrees, including
*removed* ones) into equal-count time strata and draws one substantive session per
stratum, so the sample mirrors the work over time rather than front-loading the
latest burst. Stratum membership is keyed on file mtime, which advances when a
session is resumed — so "same data + same seed → same sample" holds only if the
logs are untouched between runs. `quotes_dropped` counts evidence the verifier rejected.

The per-session observation schema (the Haiku output that feeds synthesis) lives
in `prompts/per_session_extract.md`. `strengths[]` / `gaps[]` / `friction_signals[]`
/ `context_health` are the hooks a Phase-2 recommender keys off. `profile.md` is a
human-readable rendering of both files.
