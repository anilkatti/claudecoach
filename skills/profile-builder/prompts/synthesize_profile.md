# Profile synthesis (Opus)

You receive per-session observations, an owned-capabilities inventory, a
deterministic **config-health** block, optional context files, and a provenance
block. Produce **two** evidence-grounded profiles for the CURRENT project only,
following `reference/schema.md` (schema_version 2) exactly.

The person may be in any profession (engineer, analyst, accountant, writer, …).
**Do not assume software.** "Work" is artifacts of any kind.

## Rules

- **Cite only verified quotes.** Each observation arrives with an `evidence` list
  of quotes that have already been checked to appear verbatim in a transcript.
  Every `domains` / `tools_and_materials` / `task_archetypes` / `strength` / `gap`
  / `friction_signal` you emit must reuse one of those quotes, formatted
  `session:<id> "quote"`. Never write a quote that isn't in the observations.
  **Never invent** a signal the observations don't support. No evidence → omit it.
- `weight` ∈ [0,1] reflects how strongly the evidence supports the entry.
- Express habits as `"k of n sampled sessions"` using the counts you actually see.
- Fold `signals_of_judgment` from the observations into `working_style` and
  `strengths` (with their quotes); don't drop them.
- **`gaps` and `friction_signals` are candidate signals, not recommendations.**
  Give each a `confidence`. Describe what the evidence shows; do not prescribe a
  fix or tell the person to install/remove anything — a downstream coach does that.
- **`context_health`:** copy the provided config-health JSON into
  `user.profile.context_health` **verbatim and unjudged** — it is raw signal. Do
  not editorialize, rank, or recommend inside it.
- Set `work_type` on the project from the distribution of per-session `work_type`.
- `user.profile` describes behavior **observed in this project only** (set
  `observed_in.note`). Do not generalize beyond it.
- Copy the provided provenance into each profile's `provenance`; keep the
  `disclaimer`. Be honest in `summary` about a thin sample.
- **Update mode:** if `existing_profile` is non-empty, this is a refresh, not a
  rewrite. Carry forward entries the new evidence still supports, add newly-seen
  ones, and drop or down-weight entries the new sessions contradict or no longer
  show. Re-verify against the new observations — never keep a claim just because
  it was there before. If `existing_profile` is empty, synthesize fresh.

## Output format

Output **only** the two JSON objects, each labeled exactly so they can be split:

```
===PROJECT===
{ ...project.profile.json per reference/schema.md... }
===USER===
{ ...user.profile.json per reference/schema.md... }
```

## Inputs
project_slug: {{SLUG}}
provenance: {{PROVENANCE_JSON}}
owned_capabilities: {{INVENTORY_JSON}}
config_health (copy verbatim into user.profile.context_health): {{CONTEXT_HEALTH_JSON}}
context_files (global CLAUDE.md, repo CLAUDE.md, project MEMORY.md; may be empty): {{CONTEXT}}
per_session_observations (evidence quotes are pre-verified): {{OBSERVATIONS_JSON}}
existing_profile (empty unless updating; reconcile against it per the update-mode rule): {{EXISTING_PROFILE}}
