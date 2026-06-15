# Profile synthesis (Opus)

You receive per-session observations (a JSON array), an owned-capabilities
inventory, optional context files, and a provenance/report block. Produce **two**
evidence-grounded profiles for the CURRENT project only.

## Rules
- Every `domains`/`tech_stack`/`task_archetypes`/`strengths`/`gaps` entry must
  carry `evidence` traceable to a `session:<id>` and/or a quote. **Never invent.**
- `weight` ∈ [0,1] reflects how strongly the evidence supports the entry.
- Express habits as `"k of n sampled sessions"` using the counts you actually see.
- `user.profile` describes behavior **observed in this project only** (set the
  `observed_in.note` accordingly). Do not generalize beyond it.
- Copy the provided provenance into each profile's `provenance` and keep the
  `disclaimer`.
- Follow the exact field structure in `reference/schema.md`.
- Output **only** the two JSON objects below, each labeled exactly
  `===PROJECT===` then `===USER===` so they can be split.

## Output format
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
context_files (may be empty): {{CONTEXT}}
per_session_observations: {{OBSERVATIONS_JSON}}
