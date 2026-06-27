# ClaudeCoach: richer capability discovery + real profile cleanup

**Status:** approved design, pre-plan
**Date:** 2026-06-26
**New code:** `skills/recommend-actions/reference/sources.md` (verified adoption-sources +
config-hygiene-levers methodology reference).
**Changes:** `skills/recommend-actions/prompts/` (capability_scout.md, config_doctor.md,
action_synthesizer.md) + `scripts/test_prompts.py`.
**Scope:** coach-side only. The sensor (profile-builder) already supplies everything
needed — no profile-builder change.

## Problem

Two gaps, both observed against the live cadel-mono-repo run regenerated 2026-06-26
(`~/.claude/profiles/-Volumes-Sources-cadel-mono-repo/`):

1. **Acquire is too thin — the "what do strong Claude users actually run" alpha is
   under-delivered.** `capability_scout` emitted **1** candidate (Context7) for a user
   who owns 60 skills. It only chases *spelled-out gaps* + a soft "well-known options"
   clause, dedupes hard against owned, and (after the 2026-06-26 CLI-first fix) was
   *over*-suppressing genuinely-leverageful MCP. Live research confirmed real net-new
   leverage this profile lacks — e.g. Postgres MCP Pro (structured introspection /
   index-tuning / EXPLAIN that `psql` can't hand Claude), Sentry MCP, FastAPI-MCP — that
   the scout never surfaced.

2. **Profile cleanup is buried.** The sensor flags **79 unused-in-sample capabilities**
   (36 repo / 11 personal / 32 plugin), **3 duplicates**, and **~7,980 always-on tokens**
   (`~/.claude/CLAUDE.md` 4.8KB + repo `CLAUDE.md` 11.6KB + `MEMORY.md` 15.6KB). The coach
   surfaced **one buried FYI** covering 8 plugin skills. Users want to know how to *manage
   their Claude profile to get the most out of Claude*; that alpha is sitting unused in the
   data.

### One honest recalibration of the 2026-06-26 CLI-first fix

Hygiene research (Anthropic docs, verified by fetch 2026-06-26) found **MCP tool schemas
are deferred by default** via tool search — *"adding more MCP servers has minimal impact
on your context window"* (code.claude.com/docs/en/mcp). So the *"MCP's always-on token
cost"* rationale this repo shipped earlier today in `capability_scout.md` is **largely
obsolete**. CLI-first stays — but justified by *simplicity, a tool the user already
fluently drives, and no extra server/security surface*, **not** token cost. And the scout
must **not** suppress an MCP that gives structured/programmatic leverage a CLI can't. The
real always-on tax is **skills** (name+description loaded every turn, ~1% of the context
budget, least-used dropped first) and **CLAUDE.md/memory bloat** — not MCP.

## Decisions (resolved with the user)

- **Live research, no catalog.** Enrich `capability_scout` to survey real adoption signals
  live per run; do **not** build a maintained capability catalog (keeps the 2026-06-16
  "no static catalog" decision). A *methodology* reference (which sources to query, which
  levers exist) is allowed — it doesn't rot the way a per-capability catalog would.
- **Both gaps**, coach-side only. The sensor already provides `source` (repo/personal/plugin)
  on every unused capability, `skill_usage` (sessions_seen per capability), and `always_on`
  broken down per file — enough to rank prunability and target bloat. No sensor change.
- **Deliverable: spec → plan → stop for approval.** No implementation this session.

## Research provenance (verified 2026-06-26, live web)

Three parallel research passes; full notes in the run's scratch
(`research_landscape.md`, `research_stack.md`, `research_hygiene.md`). The durable,
verified facts below move into `reference/sources.md`. Every URL was fetched; star/usage
figures are visibility signals, not adoption — see the caveat.

**Live-surveyable adoption sources**
- Official MCP Registry API — `https://registry.modelcontextprotocol.io` (machine-readable
  identity spine; *listing ≠ adoption*; path `/v0` vs `/v0.1` unconfirmed — verify live).
- PulseMCP — `https://www.pulsemcp.com/servers` (API `api.pulsemcp.com/v0.1/servers`) —
  the one source with a real **usage** proxy (est. visitors/week). Open-vs-keyed access
  unconfirmed.
- Glama — `https://glama.ai/mcp/servers` — quality **grades A–F**, weekly downloads, stars.
- Anthropic plugin marketplace — `https://github.com/anthropics/claude-plugins-official`
  (machine-readable `marketplace.json`; the only Claude-Code-scoped feed).
- GitHub stars — `api.github.com/repos/{owner}/{repo}` — pair `stargazers_count` with
  `pushed_at` (freshness).
- Curated lists — `punkpeye/awesome-mcp-servers`, `hesreallyhim/awesome-claude-code`.
- **Caveat (must encode):** stars/listings = *visibility*, not adoption. Only PulseMCP
  (visitors) and Glama (downloads) expose a real-usage proxy → triangulate; never trust a
  single star count.

**Config-hygiene levers (verified against code.claude.com/docs 2026-06-26; these keys
drift — the reference must say "re-verify against live docs")**
- `disable-model-invocation: true` — SKILL.md frontmatter; removes the description from
  context entirely, keeps `/name`. (The real cost lever for a dormant-but-wanted skill.)
- `skillOverrides` — `.claude/settings.local.json`; states `on | name-only |
  user-invocable-only | off`; absent = `on`. **Plugin skills are exempt.** (Use to
  suppress a *team/repo* skill for yourself, local-only.)
- `paths:` frontmatter — path-scope a skill so it only loads where relevant.
- `user-invocable: false` is **not** a cost lever (description stays in context).
- MCP is deferred by default; `alwaysLoad: true` opts a server *into* upfront cost.
- CLAUDE.md: target **< 200 lines**; bloat makes Claude *ignore* instructions
  (code.claude.com/docs/en/memory, /best-practices). MEMORY.md loads first 200 lines/25KB.
- **Dead-weight vs dormant test:** run a representative prompt with the skill available and
  again with it disabled; unchanged output = dead weight, degraded = load-bearing.
  `/doctor` shows which descriptions are being dropped/shortened.
- **Team vs personal:** repo `.claude/skills`, `.mcp.json`, project `CLAUDE.md` are shared —
  *don't delete*; suppress for yourself via `skillOverrides` (local). Personal =
  `~/.claude/...` — the user's to prune.

**Stack-fit for this profile (illustrative, not hardcoded):** net-new worth-it = Postgres
MCP Pro, Sentry MCP, FastAPI-MCP, (SSH MCP — vet), Context7; CLI-redundant skip = GitHub,
Docker, Filesystem, Git, Memory, Brave/Search (Playwright + promptfoo already owned).
Security caveats surfaced: a June-2026 Sentry "agentjacking" report (unverified) and
unaudited community SSH servers — the scout must flag such caveats, never bury them.

## Architecture

```
   profile-builder profile  ──(unchanged: source, skill_usage, always_on per-file)──┐
                                                                                     ▼
   reference/sources.md  ─cited by─►  capability_scout.md   (Gap A: richer acquire)  │
   (verified sources + levers)   └─►  config_doctor.md      (Gap B: real cleanup)    │
                                              │                                       │
                                              ▼                                       ▼
                                       candidate actions  ──►  action_synthesizer.md ──► actions.json
                                                                (surface alpha; not buried in FYI)
```

Everything is a **prompt/reference change** the existing pipeline already routes. No new
scripts, no schema change, no sensor change.

## Component 1 — `reference/sources.md` (NEW; methodology, not a catalog)

Two sections, carrying the verified content above: **(A) Adoption sources** a live scout
can survey (URLs, what signal each gives, which expose real usage, the triangulation
caveat) and **(B) Config-hygiene levers** (exact keys, where each lives, the plugin-exempt
and not-a-cost-lever caveats, CLAUDE.md size guidance, the dead-weight-vs-dormant test,
team-vs-personal). It opens with a standing instruction: **these keys/paths/endpoints
drift — re-verify against the linked live docs before asserting them in a recommendation.**
It lists *sources and levers*, never a frozen list of "recommended capabilities."

## Component 2 — `capability_scout.md` (Gap A)

- **Proactive adoption survey.** Beyond literal gap-fillers, survey the `reference/sources.md`
  sources live for the profile's `domains`/`task_archetypes` and surface high-adoption,
  well-maintained capabilities the user **lacks** — the "what strong users in your stack
  run" angle. Each such candidate must cite a **real adoption signal** (Glama grade /
  PulseMCP usage / stars+`pushed_at`), not bare existence, and still WebFetch-verify its URL.
- **Recalibrate CLI-vs-MCP.** Remove the "MCP always-on token cost" argument (obsolete —
  MCP is deferred-cheap). Keep CLI-first, justified by *simplicity / a CLI you already
  fluently drive / no extra server+security surface*. Explicitly: do **not** suppress an
  MCP that delivers structured/programmatic leverage a CLI can't (name Postgres-style
  introspection as the example class).
- **Rails unchanged:** URL-verify every candidate, dedupe against `owned_capabilities`,
  scope to this profile, and **surface security caveats** (unaudited community servers,
  known advisories) rather than burying them.
- **Cost is bounded by the existing cache.** The richer survey is *not* a new per-run web
  cost: the acquire lane already caches `capability_scout`'s output per profile (14-day TTL,
  `cache.py`), so the live survey runs only when that cache is refreshed — exactly as today.
  No change to the caching mechanism.

## Component 3 — `config_doctor.md` (Gap B)

- **Promote unused cleanup from a footnote to a real lens.** Build a **prioritized prunable
  subset** of `unused_capabilities`, ranked by *zero `skill_usage` hits* (dormant in the
  whole sample) and grouped by `source`.
- **Team vs personal, explicit.** repo-`source` capabilities are team-shared — never
  recommend deleting; at most *suppress for yourself* via `skillOverrides` (local).
  personal/plugin-`source` are the user's to prune. Plugin skills are `skillOverrides`-exempt
  (lever = disable/uninstall the plugin or accept deferred-cheap).
- **Right verified lever per case** (from `reference/sources.md`): dormant-but-wanted →
  `disable-model-invocation` or `skillOverrides: name-only`; irrelevant-here →
  `skillOverrides: off` (local) or `paths:` scoping; true same-scope dup/dead weight →
  archive. Keep the 2026-06-26 **cross-scope-duplicate guardrail** (personal scope is
  global; don't archive the personal copy of a personal↔repo/plugin pair).
- **Quantify the true tax.** Target the always-on **bloat** with the per-file numbers from
  `always_on.sources` and the verified `< 200 lines` CLAUDE.md guidance (here: repo
  `CLAUDE.md` 11.6KB + `MEMORY.md` 15.6KB are the hogs). **De-emphasize MCP footprint** —
  call it deferred-cheap, not a context hog.
- **Honesty rails kept:** "unused" = "unused in the sampled sessions"; removals reversible;
  the dead-weight-vs-dormant call is the user's (recommend the *reversible* lever, suggest
  the A/B test), never asserted as "dead."

## Component 4 — `action_synthesizer.md` (light prioritization tweak)

The regen still parked cleanup in FYI and acquire in Consider. Add: high-confidence
**acquire** finds (real adoption signal + a clear unmet need) and **high-tax cleanup**
(big always-on trim, or a clearly-irrelevant-here capability) are eligible for
`do_now`/`consider` — they must not be reflexively demoted below `capture_context`. This
extends the existing "don't let one family crowd out installs/habits" balancing.

## Testing strategy

LLM-free, offline, structural (the existing `test_prompts.py` pattern).

- **New** `test_sources_reference_exists`: `reference/sources.md` exists and contains the
  key levers (`disable-model-invocation`, `skillOverrides`) and at least the registry +
  PulseMCP + Glama source names, plus the "re-verify against live docs" caveat string.
- **`test_capability_scout`**: assert the adoption-survey lens (`reference/sources.md`
  referenced; an "adoption signal" requirement) and the **recalibrated** CLI framing —
  i.e. the old `"token cost"` assertion is replaced by one asserting MCP is framed as
  deferred/minimal-context and CLI-first rests on simplicity; the URL-verify / dedupe /
  scope rails remain asserted.
- **`test_config_doctor`**: assert the unused-cleanup lens (uses `skill_usage`,
  team-vs-personal language, `disable-model-invocation`/`skillOverrides`/`paths`), the
  always-on bloat targeting (`always_on` + the `< 200` CLAUDE.md guidance), and the
  preserved cross-scope-duplicate guardrail ("deliberately global", "keep them in sync").
- **`test_synthesizer`**: assert acquire/cleanup can reach `do_now`/`consider` (the
  crowd-out / eligibility language).

## Sequencing

1. `reference/sources.md` + its test (the shared dependency both prompts cite).
2. `capability_scout.md` (Gap A) + updated scout tests.
3. `config_doctor.md` (Gap B) + updated doctor tests.
4. `action_synthesizer.md` tweak + test.
5. (Verification, not in this spec's build) regenerate cadel-mono-repo from the working
   copy to confirm the richer acquire set + the promoted cleanup appear.

## Out of scope / non-goals

- No maintained capability catalog (decided against; live survey stays the source).
- No profile-builder/sensor change — it already carries `source`, `skill_usage`, and
  per-file `always_on`.
- No new scripts, no `actions.json` schema change, no change to the interactive Apply UI
  shipped earlier today.
- Not hardcoding specific capability names into prompts — the stack-fit list above is
  illustrative grounding, not a checklist to embed (it would rot).

## Invariants preserved

Sensor → coach → executor separation (this is all coach); evidence-verified, URL-cited,
never assert capability/lever facts from memory (the reference says re-verify live);
audience-neutral; "unused" = "unused in the sample"; removals reversible and opt-in;
scope every recommendation to *this* profile; the 2026-06-26 cross-scope-duplicate
guardrail stays.
