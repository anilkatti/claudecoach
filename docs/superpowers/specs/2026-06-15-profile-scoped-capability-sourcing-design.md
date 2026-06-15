# Profile-scoped, live, cached capability sourcing

**Status:** approved design, pre-plan
**Date:** 2026-06-15
**Skill affected:** `skills/recommend-actions/` (the **acquire** path only)
**Supersedes (partially):** the static-index portion of
`docs/superpowers/specs/2026-06-15-recommend-actions-design.html`

## Problem

`recommend-actions` was built to match a user's gaps against a **static, broad,
audience-neutral** `reference/capabilities_index.json`, refreshed offline by
`build_indexes.py`. Two problems:

1. **The index is empty** (`{"built_at": "seed", "capabilities": []}`), so the
   `capability_scout` specialist has nothing to recommend — the marquee use case
   ("what skills/MCP should I install?") returns nothing.
2. **A broad pre-built catalog is the wrong model.** Keeping legal / finance /
   writing capabilities cached for a software engineer is dead weight. We should
   fetch **only what is relevant to *this* profile**, and only **after** the
   profile exists.

## Decision

Replace the static broad catalog with **live, profile-scoped capability research,
cached per project.** Only the **acquire** lane changes; `config`, `author`, and
`behavior` are untouched. This is a small refactor + one new plumbing module, not
a rewrite.

## Architecture

```
load_profile ──► lanes (acquire gains `work_type`)
       │
       ▼
  cache.py status  ──── fresh? ───────────────────────────────┐
   (per-project)         │ yes: reuse cached candidates        │
       │ no / stale      │ (no network needed)                 │
       ▼                 ▼                                      ▼
  network consented? ──► capability_scout (Opus, live web) ──► cache.py write
   │ no                    · search scoped to work_type/domains/    (per-project)
   ▼                         task_archetypes/gaps                   │
  reuse stale cache if      · WebFetch-verify every URL             │
  present (warn), else      · dedupe vs owned_capabilities          │
  skip acquire (honest)     · never invent a name/URL                │
       │                                                             │
       └───────────────┬───────────────────────────────────────────┘
                       ▼
        acquire candidates  ──►  action_synthesizer (unchanged)  ──► actions.json
        (config/author/behavior specialists run in parallel, unchanged)
```

The freshness branch:

```
cache exists for <slug>?
 ├─ no  → research live (if network) → write cache
 └─ yes → cache.profile_generated_at == profile.generated_at  AND  age < 14d?
          ├─ yes → reuse cached candidates (offline OK)
          └─ no  → re-research live (if network) & overwrite
                   else → use stale cache + warn the user
```

## Components

### New: `scripts/cache.py` (plumbing, LLM-free)

The only reader/writer of `~/.claude/profiles/<slug>/capabilities_cache.json`.
Deterministic; no judgment.

Cache file schema:
```json
{
  "schema_version": 1,
  "fetched_at": "<ISO8601>",
  "profile_generated_at": "<ISO8601>",
  "network_used": true,
  "candidates": [ /* acquire-family candidate actions, scout's verified output */ ]
}
```

Functions:
- `cache_path(profile_dir)` → the json path.
- `load_cache(profile_dir)` → dict or `None`.
- `is_fresh(cache, profile_generated_at, now_iso, ttl_days=14)` → bool — true only
  when `cache["profile_generated_at"] == profile_generated_at` **and**
  `age(fetched_at) < ttl_days`.
- `write_cache(profile_dir, candidates, profile_generated_at, network_used, now_iso)`
  → writes the file, returns the path.
- CLI `status`: prints `{exists, fresh, fetched_at, count, network_used}` for
  `SKILL.md` to branch on. CLI `write`: persists a candidates JSON file.

TTL reuses the existing 14-day staleness convention already in `load_profile.py`.

### Changed: `scripts/load_profile.py`

Add `work_type` to the **acquire** lane (`split_lanes`) so the scout knows what
kind of work to scope its search to. One-line addition; everything else stands.

### Rewritten: `prompts/capability_scout.md`

- **Remove** `{{INDEX_JSON}}`. **Add** the scoped profile fields (`work_type`,
  `domains`, `task_archetypes`, gaps) — already in the acquire lane.
- With network: run web searches **bounded to the profile's scope**; for every
  candidate, **WebFetch the URL to confirm it resolves** before emitting it;
  dedupe against `owned_capabilities`; `source.kind: "live_web"`, real `url`,
  `source.freshness` = fetch date.
- Without network: emit `[]` and a one-line note that acquire needs a live lookup.
- **Honesty rail stays load-bearing:** never emit a capability whose URL was not
  verified this run. No invented names.

### Changed: `SKILL.md`

- **Step 0 consent gate** reframed: finding new skills/MCP/plugins needs a
  one-time **live, profile-scoped** lookup (cached afterward); declining still
  yields config/author/behavior advice fully offline.
- **Step 2 acquire branch** becomes cache-aware: `cache.py status` → reuse cached
  candidates, or dispatch the scout live and `cache.py write` its output. The
  other three specialists dispatch exactly as today.

### Trimmed: `scripts/build_indexes.py` + `reference/`

- Remove the **capabilities** half (`normalize_capability`, `build_capabilities`,
  capability seed) and delete the empty `reference/capabilities_index.json` — my
  change orphans them.
- **Keep** `best_practices.json` and the practices half: those are general
  Claude-usage principles (plan-first, verify-before-done) the `practice_coach`
  still needs — not an audience-specific capability catalog.

### Changed: `scripts/render.py`, `reference/schema.md`, synthesizer META

`actions.json` meta currently carries `indexes.capabilities_built_at`. Repoint it
to the cache: `capabilities_fetched_at` (from the cache, or `"live"` / `"none"`
when the lane was skipped). `render.py` displays it; `schema.md` documents the
cache file + the new meta field; the synthesizer's `{{META_JSON}}` is updated to
match. `best_practices_built_at` is unchanged.

## Data flow contract (unchanged downstream)

The scout still emits the **same candidate-action shape** (`family: "acquire"`)
defined in `reference/schema.md`; only its *source* (live + cached vs static
index) changes. The synthesizer, render, and apply loop need no logic change
beyond the meta field rename.

## Testing

LLM-free, offline, fast — matching the existing suite:

- **New `test_cache.py`:** write→read round-trip; `is_fresh` true on
  matching `profile_generated_at` within TTL; false when the profile's
  `generated_at` changed; false when aged past TTL; `status` CLI JSON; `write`
  CLI persists.
- **`test_load_profile.py`:** assert `work_type` is present in the acquire lane.
- **`test_prompts.py`:** scout prompt no longer references `{{INDEX_JSON}}`, still
  carries the evidence + "never invent / verify the URL" rails and the
  untrusted-data guard; drop the capabilities assertions.
- **`test_build_indexes.py`:** drop capabilities cases; keep practices cases.
- **`test_render.py` / schema:** meta shows `capabilities_fetched_at`.

## The payoff: end-to-end run

After the refactor is green, run `/recommend-actions` on **this repo's existing
profile** with network **on**:
- exercises the full multi-agent flow (scout live + 3 specialists → synthesizer →
  render) for the first time,
- verifies the cache is written and a second run reuses it offline,
- produces a real `actions.json` / `actions.html` to eyeball for sanity
  (every acquire action cites a verified URL; nothing audience-irrelevant).

This is also the project's first true integration check of Phase 2 against live
LLM output, not just the Python plumbing.

## Honesty rails (preserved / strengthened)

- Read-only and offline by default; network and each apply are separately consented.
- Acquire recommendations require a live lookup; declining is honestly surfaced,
  not silently empty.
- Every acquire action cites a **URL verified this run** (or reused from a cache
  that verified it) — never an invented name.
- "unused" still means "unused in the sampled sessions"; removals reversible.

## Out of scope

- A user-level shared cache across projects (we chose per-project).
- Rebuilding a broad multi-audience catalog.
- Phases 3 (Reorganize as a separate skill) and 4 (Monitor).
