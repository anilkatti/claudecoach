# /profile-builder v2 — Enhancement (addendum)

**Date:** 2026-06-15
**Status:** Implemented
**Supersedes parts of:** `2026-06-14-profile-builder-design.md` (v1)

## Why

v1 was a solid, tested *describer*, but as the **sensor for a Claude coach** it
had three structural gaps (found in review): it equated "work" with code (useless
for non-developers), it collected nothing for Goal 2 (reduce context
bloat/contradictions), and it **could not satisfy its own evidence contract** —
synthesis was asked to cite verbatim quotes it never received and nothing verified
them. v2 reframes the skill as a coach **sensor**: richer, audience-neutral,
evidence-*verified* signals that downstream skills turn into recommendations.

## Decisions (from user interview, 2026-06-15)

1. **Scope:** full sensor upgrade (generalize for any audience + friction/outcome
   + config-health + fix the evidence/correctness bugs). *Not* maximal — no
   trend-over-time, no cross-project merge.
2. **Goal-2 config signals:** **collect, don't judge.** profile-builder gathers
   raw config-health signals; a downstream coach recommends.
3. **Interview:** **pure passive** — infer everything from transcripts + config;
   ask the user nothing. (Raises the bar on content-level inference.)

## What changed (vs v1)

```
prepare ──┬─ neutral + friction facts (artifacts by material type, tool_errors,
          │  duration_seconds), total condensed cap + truncation flag
          │
inventory ─┘                         context_health.py  ✚ NEW (deterministic)
                                      always-on sizes · hooks · duplicate /
Haiku/session ✚ work_type, neutral   overlapping / unused capabilities · MCP
  vocab, attribution discipline,            │
  friction/outcome, leverage,          verify_quotes ✚ (sessions.py verify)
  per-observation verbatim quotes ─────────┘ drops any cited quote not present
          │                                  verbatim in a transcript
          └────────────► Opus synthesis (neutral; cites verified bank only;
                          folds context_health in raw) ──► v2 profiles
```

- **Audience-neutral schema (v2):** `work_type` added; `tech_stack` →
  `tools_and_materials` (non-code counts); neutral `intent`/`verification` enums.
- **Friction/outcome:** deterministic (`tool_errors`, `duration_seconds`, artifact
  buckets) + LLM (`outcome`, `rework`, `reexplained_context`).
- **`leverage`** now produced per session (v1 declared it but never extracted it).
- **`context_health`** block in `user.profile.json` (raw signals, no verdicts).
- **Evidence contract fixed:** quotes are verbatim, **verified deterministically**;
  `quotes_verified`/`quotes_dropped` recorded in provenance.
- **Honesty fixes:** correct `MEMORY.md` path (`~/.claude/projects/<slug>/memory/`,
  not `<repo>/MEMORY.md`); determinism caveat (recent set is mtime-based);
  `reference/limitations.md` coverage register added.

## Out of scope (unchanged from v1 + this round)

Skill recommendation / config *organization* (downstream), cross-project merge,
trend over time, deterministic *scoring* (interpretation stays LLM; only
*collection* is deterministic), the user-interview step.

## Correction to the v1 review

The review claimed `inventory.py` dedup *hides* cross-level duplicate skills. It
does not — it dedups within a `(name, source)` key, so the same skill at different
levels survives as distinct entries. Duplicate detection therefore lives in
`context_health.find_duplicate_capabilities`, not an inventory change.

## Verification

`python -m pytest skills/profile-builder/scripts/` — 40 tests (sessions,
inventory, context-health, evidence verification), incl. a non-dev
(spreadsheet/accountant) fixture. Dry-run on this repo surfaced a real duplicate
(`frontend-design` at personal + plugin), ~1.3k always-on tokens, and the two
active hooks.
