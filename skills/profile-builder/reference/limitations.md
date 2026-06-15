# profile-builder — limitations register

What this sensor does **not** capture, so downstream coaches (and the user) don't
over-trust it. Read before presenting a profile as authoritative.

## Interpretation is LLM, so it varies
- Per-session reads (Haiku) and synthesis (Opus) are **nondeterministic** —
  re-runs of the same data differ. The seeded sample is reproducible only while
  the logs are untouched (the recent set is keyed on file mtime, which advances
  when a session is resumed).
- The fast tier reads each session in isolation; subtle human-vs-Claude
  attribution can be imperfect. Synthesis sees the observations + verified quotes,
  **not** the raw transcripts, so it can't re-derive missed evidence.

## Evidence verification has a ceiling
- `sessions.py verify` proves a cited quote **appears** in a transcript. It does
  **not** prove the quote *supports* the claim it's attached to — a real quote can
  still anchor a stretchy interpretation. `confidence` and human review mitigate.

## Sampling and scope
- Sessions are weighted **equally regardless of size**, so "k of n sessions"
  treats a 2-turn and a 200-turn session alike.
- **Current project only.** This is not a global user profile; cross-project merge
  is deferred. `observed_in.note` marks the limitation.
- Thin-sample projects yield noisy profiles; the summary/provenance must say so.

## Config-health is approximate signal, not measurement
- `overlapping_capabilities` is **lexical** (Jaccard over description words): it
  can miss semantically-similar wording and over-flag shared jargon.
- Always-on / hook / MCP cost is proxied by **sizes and counts**, not measured
  token footprint. MCP tool-definition token cost is not computed.
- `duration_seconds` is wall-clock between first and last timestamp; it includes
  idle/away time, not active effort.

## Not captured at all (by design, this phase)
- Trend over time, cost/latency telemetry, and any cross-project or non-Claude-Code
  work.

## Secret scrubbing
- Regex-based; novel token formats can slip through. Raw transcripts never leave
  the machine — only condensed, scrubbed text and verified quotes reach a model.
