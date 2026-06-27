# Richer Capability Discovery + Real Profile Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ClaudeCoach's coach surface (a) what high-adoption capabilities strong Claude users in your stack run that you lack, and (b) the real unused/bloat cleanup sitting in your profile — by enriching three specialist prompts against one verified methodology reference.

**Architecture:** Pure prompt + reference change (no scripts, no schema, no sensor change). A new `reference/sources.md` carries verified adoption *sources* and config-hygiene *levers*; `capability_scout.md` surveys those sources and recalibrates CLI-vs-MCP; `config_doctor.md` promotes unused/bloat cleanup from a footnote to a real lens; `action_synthesizer.md` lets that alpha reach `do_now`/`consider`.

**Tech Stack:** Markdown prompts; Python `pytest` structural tests (LLM-free). No new dependencies.

## Global Constraints

- **Coach-side only** — no `profile-builder`/sensor change, no new scripts, no `actions.json` schema change. The sensor already provides `source` (repo/personal/plugin) on unused capabilities, `skill_usage` (sessions_seen), and per-file `always_on.sources`.
- **No maintained capability catalog** — `reference/sources.md` lists *sources and levers* (methodology), never a frozen list of recommended capabilities.
- **Never assert capability/lever facts from memory** — the reference is grounded in pages fetched 2026-06-26 and carries a standing "re-verify against live docs, these drift" caveat. Star/listing counts are *visibility, not adoption* — triangulate.
- **Tests are structural, LLM-free, offline**; run per-skill from `skills/recommend-actions` with `python -m pytest scripts/ -q`. Every existing `test_prompts.py` assertion must stay green except the one explicitly replaced in Task 2.
- **Honesty rails preserved**: "unused" = "unused in the sampled sessions"; removals reversible/opt-in; correlational habit language; scope every recommendation to *this* profile; keep the 2026-06-26 cross-scope-duplicate guardrail ("personal scope is deliberately global").
- **Audience-neutral** copy.

---

### Task 1: `reference/sources.md` — verified sources + levers

**Files:**
- Create: `skills/recommend-actions/reference/sources.md`
- Test: `skills/recommend-actions/scripts/test_prompts.py`

**Interfaces:**
- Produces: a reference file both `capability_scout.md` and `config_doctor.md` cite by the relative path `reference/sources.md`. Key strings later tasks/tests rely on: `disable-model-invocation`, `skillOverrides`, `PulseMCP`, `Glama`, `registry.modelcontextprotocol.io`, `200 lines`, `deferred by default`, `visibility, not adoption`, and the caveat phrase `re-verify`.

- [ ] **Step 1: Write the failing test**

Add to `skills/recommend-actions/scripts/test_prompts.py` (after the imports/`_read`):

```python
REFERENCE = os.path.join(os.path.dirname(__file__), "..", "reference")


def _read_ref(name):
    with open(os.path.join(REFERENCE, name)) as f:
        return f.read()


def test_sources_reference_lists_sources_and_levers():
    text = _read_ref("sources.md")
    low = text.lower()
    # adoption sources (incl. the two real-usage proxies) + the registry
    assert "registry.modelcontextprotocol.io" in text
    assert "pulsemcp" in low and "glama" in low
    assert "anthropics/claude-plugins-official" in text
    # the verified hygiene levers, by exact key
    assert "disable-model-invocation" in text
    assert "skillOverrides" in text and "settings.local.json" in text
    assert "paths:" in text
    # verified guidance + the standing caveats
    assert "200 lines" in low                       # CLAUDE.md size discipline
    assert "deferred by default" in low             # MCP is not a context hog
    assert "visibility, not adoption" in low        # triangulation caveat
    assert "re-verify" in low                       # keys drift
    assert "plugin skills are exempt" in low        # skillOverrides exemption
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py::test_sources_reference_lists_sources_and_levers -v`
Expected: FAIL (`FileNotFoundError: …/reference/sources.md`).

- [ ] **Step 3: Create the reference**

Create `skills/recommend-actions/reference/sources.md`:

```markdown
# Capability-discovery sources & config-hygiene levers

**Verified 2026-06-26 by live fetch.** These endpoints, keys, and figures **drift** —
**re-verify** against the linked live docs before asserting any of them in a recommendation.
Star/listing counts measure **visibility, not adoption**; triangulate, never trust a single
star count.

## A. Adoption sources a live scout can survey (scoped to the profile's domains)

| Source | URL | Signal | Notes |
|---|---|---|---|
| Official MCP Registry | https://registry.modelcontextprotocol.io | canonical identity (name/repo/remotes) | listing != adoption; path `/v0` vs `/v0.1` unconfirmed — verify live |
| PulseMCP | https://www.pulsemcp.com/servers (`api.pulsemcp.com/v0.1/servers`) | **real usage** — est. visitors/week | best adoption proxy; open-vs-keyed access unconfirmed |
| Glama | https://glama.ai/mcp/servers | **quality grade A–F** + weekly downloads + stars | second real-usage proxy |
| Anthropic plugin marketplace | https://github.com/anthropics/claude-plugins-official | official Claude-Code plugin feed (`marketplace.json`) | only Claude-Code-scoped feed |
| GitHub stars | `api.github.com/repos/{owner}/{repo}` | `stargazers_count` + `pushed_at` (freshness) | visibility only; pair with `pushed_at` |
| awesome-lists | `punkpeye/awesome-mcp-servers`, `hesreallyhim/awesome-claude-code` | curated breadth | staleness varies |

**Triangulation rule:** prefer a capability with a real-usage proxy (PulseMCP visitors /
Glama downloads-or-grade) AND recent `pushed_at` AND official/maintained status. A high star
count alone is **visibility, not adoption**.

## B. Config-hygiene levers (verified against code.claude.com/docs 2026-06-26 — re-verify; keys drift)

- **MCP is deferred by default.** Tool schemas load via tool search; "adding more MCP servers
  has minimal impact on your context window" (code.claude.com/docs/en/mcp). MCP footprint is
  **not** a context hog. `alwaysLoad: true` opts a server into upfront cost.
- **Skills are the always-on tax.** Each skill's name+description loads every turn (budget
  ~1% of context; least-used descriptions dropped first; ~1,536-char cap per skill) —
  code.claude.com/docs/en/skills.
- `disable-model-invocation: true` — SKILL.md frontmatter; removes the description from
  context, keeps `/name`. The cost lever for a dormant-but-wanted standalone skill.
- `skillOverrides` — `.claude/settings.local.json`; states `on | name-only |
  user-invocable-only | off` (absent = `on`). **Plugin skills are exempt.** Use to suppress a
  team/repo skill for yourself, local-only.
- `paths:` — SKILL.md frontmatter; path-scope a skill so it only loads where relevant.
- `user-invocable: false` is **not** a cost lever (the description stays in context).
- **CLAUDE.md / memory:** target **< 200 lines** per CLAUDE.md; bloat makes Claude *ignore*
  instructions (code.claude.com/docs/en/memory, /best-practices). MEMORY.md loads first 200
  lines / 25KB. Per-line test: "would removing this cause a mistake? if not, cut it."
- **Dead-weight vs dormant test:** run a representative prompt with the skill available and
  again disabled; unchanged output = dead weight, degraded = load-bearing. `/doctor` shows
  which descriptions are dropped/shortened.
- **Team vs personal:** repo `.claude/skills`, `.mcp.json`, project `CLAUDE.md` are shared —
  don't delete; suppress for yourself via `skillOverrides` (local). Personal = `~/.claude/...`
  — the user's to prune.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py -v`
Expected: PASS (new test green; all existing tests still green — no prompt changed yet).

- [ ] **Step 5: Commit**

```bash
git add skills/recommend-actions/reference/sources.md skills/recommend-actions/scripts/test_prompts.py
git commit -m "feat(recommend-actions): add verified adoption-sources + hygiene-levers reference"
```

---

### Task 2: `capability_scout.md` — adoption survey + CLI-vs-MCP recalibration (Gap A)

**Files:**
- Modify: `skills/recommend-actions/prompts/capability_scout.md` (the CLI bullet, lines 29–36; the "Surface strong, well-known options" section, lines 38–45)
- Test: `skills/recommend-actions/scripts/test_prompts.py` (replace `test_capability_scout_is_cli_first`; add one test)

**Interfaces:**
- Consumes: `reference/sources.md` (Task 1).
- Produces: a scout brief that surveys adoption sources and cites a real adoption signal, and recalibrated CLI-vs-MCP guidance (no token-cost argument).

- [ ] **Step 1: Replace the cli-first test and add the survey test**

In `skills/recommend-actions/scripts/test_prompts.py`, **replace** the whole `test_capability_scout_is_cli_first` function with:

```python
def test_capability_scout_cli_first_recalibrated():
    text = _read("capability_scout")
    low = text.lower()
    assert "cli" in low and "genuinely can't" in low          # CLI-first kept
    assert "simplicity" in low                                 # justified by simplicity, not token cost
    assert "deferred by default" in low or "minimal impact" in low   # MCP is deferred-cheap
    # the obsolete token-cost rationale for refusing an MCP is gone
    assert "always-on tool-schema token cost" not in low
    # don't suppress structurally-leverageful MCP
    assert "structured/programmatic access" in low


def test_capability_scout_surveys_adoption_sources():
    text = _read("capability_scout")
    low = text.lower()
    assert "reference/sources.md" in text                      # cites the methodology reference
    assert "adoption signal" in low                            # must cite a real signal
    assert "pulsemcp" in low or "glama" in low                 # a real-usage proxy named
    assert "visibility, not adoption" in low                   # triangulation caveat
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py::test_capability_scout_cli_first_recalibrated scripts/test_prompts.py::test_capability_scout_surveys_adoption_sources -v`
Expected: FAIL (`simplicity`/`reference/sources.md`/`adoption signal` not yet present).

- [ ] **Step 3: Recalibrate the CLI-vs-MCP bullet**

In `prompts/capability_scout.md`, replace the bullet that currently begins
`- **A CLI you already use is the default — make an MCP earn its place.**` (through the line
ending `an MCP for a live-data/tool gap a CLI can't fill.`) with:

```
- **A CLI you already fluently drive is the default — but judge it on the right basis.**
  Before proposing an MCP, check `tools_and_materials` and `owned_capabilities` for an existing
  CLI that already covers the gap (e.g. `gh`, `docker`, `aws`). Prefer that CLI when it does —
  for **simplicity** (a tool the user already drives, no extra server to run, no new security
  surface), **not** for token cost: per `reference/sources.md`, MCP tool schemas are *deferred
  by default* and have minimal impact on the context window, so MCP footprint is **not** a
  reason to refuse one. Recommend an MCP when it gives something the CLI genuinely can't —
  **structured/programmatic access** the model can't reliably parse from CLI text (e.g.
  Postgres-style schema introspection / EXPLAIN / index tuning), or a materially tighter loop.
  Do **not** suppress a structurally-leverageful MCP just because a related CLI exists. Map the
  gap to the right form: a skill for a procedure, a plugin for a bundle, an MCP for a
  live-data/tool gap a CLI can't fill.
```

- [ ] **Step 4: Add the adoption-survey lens**

In `prompts/capability_scout.md`, replace the section that currently begins
`## Surface strong, well-known options — not only literal gap-fillers` (through the line ending
`Prefer established, maintained options over obscure ones.`) with:

```
## Surface what strong users in your stack run — not only literal gap-fillers
Within the profile's scope, also recommend **widely-adopted, well-known, well-maintained**
capabilities the person lacks even when no gap is spelled out — the "what do strong Claude
users in your stack actually run" angle. Survey the adoption sources in `reference/sources.md`
(the MCP registry; PulseMCP and Glama for *real usage*; the Anthropic plugin marketplace;
GitHub stars **with** `pushed_at`; the awesome-lists), scoped to a high-weight `domain` /
`task_archetype`. Each such candidate must **cite a real adoption signal** in its rationale —
a Glama grade, a PulseMCP usage figure, or stars with recent `pushed_at` — not bare existence;
a star count is **visibility, not adoption**, so triangulate. The rails are unchanged: scoped
to this profile, not already owned (dedupe against `owned_capabilities`), and **fetch and
verify its URL** before emitting it — never an invented name or an unverified URL. Flag any
security caveat (an unaudited community server, a known advisory) in the rationale rather than
burying it.
```

- [ ] **Step 5: Run the full prompt test suite**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py -v`
Expected: PASS. The recalibrated + survey tests are green; `test_capability_scout_is_live_scoped_no_static_index` (asserts no `{{INDEX_JSON}}`, `work_type`, `verify`, `never`+`invent`) and `test_capability_scout_surfaces_wellknown_options` (asserts `well-known`, `verify`, `never`+`invent`) stay green because the new copy retains "well-known", "verify", and "never an invented name".

- [ ] **Step 6: Commit**

```bash
git add skills/recommend-actions/prompts/capability_scout.md skills/recommend-actions/scripts/test_prompts.py
git commit -m "feat(capability-scout): survey adoption sources; recalibrate CLI-vs-MCP (MCP is deferred-cheap)"
```

---

### Task 3: `config_doctor.md` — the profile-management cleanup lens (Gap B)

**Files:**
- Modify: `skills/recommend-actions/prompts/config_doctor.md` (insert a new section after the reorganize block, before `## Honesty rails`)
- Test: `skills/recommend-actions/scripts/test_prompts.py` (add one test)

**Interfaces:**
- Consumes: `reference/sources.md` (Task 1); sensor fields `unused_capabilities[].source`, `skill_usage`, `always_on.sources`.
- Produces: a config brief that surfaces a prioritized prunable subset (team-vs-personal) and targets always-on bloat by file.

- [ ] **Step 1: Write the failing test**

Add to `skills/recommend-actions/scripts/test_prompts.py`:

```python
def test_config_doctor_profile_management_lens():
    text = _read("config_doctor")
    low = text.lower()
    assert "skill_usage" in text                        # ranks the prunable subset by usage
    assert "reference/sources.md" in text               # levers come from the reference
    # team vs personal: repo not the user's to delete; suppress-for-self lever + location
    assert "team-shared" in low
    assert "settings.local.json" in low
    # always-on bloat targeting + verified size guidance
    assert "always_on.sources" in text
    assert "200 lines" in low
    # MCP de-emphasized (deferred-cheap)
    assert "minimal context impact" in low or "deferred by default" in low
    # honesty rail preserved
    assert "sampled sessions" in low
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py::test_config_doctor_profile_management_lens -v`
Expected: FAIL (`skill_usage`/`team-shared`/`always_on.sources` not yet present).

- [ ] **Step 3: Insert the profile-management lens**

In `prompts/config_doctor.md`, immediately **before** the line `## Honesty rails`, insert this new section (a blank line before and after):

```
## The profile-management lens — surface the cleanup the user actually has
This is high-value alpha, not a footnote. Two moves, both grounded in `reference/sources.md`
(treat its keys as drift-prone — re-verify):

1. **Unused-capability cleanup (prioritized, honest).** From `unused_capabilities`, build a
   *prioritized prunable subset* — rank by **no `skill_usage` hit at all** (dormant across the
   whole sample) and group by `source`:
   - **`source: repo` (team-shared)** — NOT the user's to delete. At most recommend
     *suppressing it for themselves* via `skillOverrides` (`off` / `name-only`) in
     `.claude/settings.local.json` (local-only), and only when it is clearly irrelevant to
     their work. Never `archive` a repo/team capability.
   - **`source: personal`** — the user's to prune: `disable-model-invocation` (dormant but
     wanted) or `skillOverrides` / `paths:` scoping, or `archive` only if the evidence shows
     it is truly dead.
   - **`source: plugin`** — `skillOverrides` is **exempt** for plugin skills; the lever is
     disabling/uninstalling the plugin, or leaving it (deferred-cheap). Say which.
   Recommend the **reversible** lever and suggest the dead-weight-vs-dormant A/B test (run a
   representative prompt with the skill available vs disabled; unchanged = dead weight) — the
   call is the user's; never assert "dead." "unused" stays "unused in the sampled sessions."
2. **Always-on bloat is the real token hog — target it by file.** Use `always_on.sources`
   (per-file `chars` / `est_tokens`) to name the specific bloated file (repo `CLAUDE.md`,
   `~/.claude/CLAUDE.md`, or `MEMORY.md`) and recommend trimming it toward the documented
   **< 200 lines per CLAUDE.md** (bloat makes Claude *ignore* instructions). This is where the
   real `tokens_saved` lives. **De-emphasize `mcp_footprint`** — MCP tool schemas are deferred
   by default and have **minimal context impact**, so it is not a context hog (only flag an MCP
   with `alwaysLoad: true`).
```

- [ ] **Step 4: Run the full prompt test suite**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py -v`
Expected: PASS. The new lens test is green; the existing config_doctor tests stay green —
`test_config_doctor_skill_hygiene_levers` (`disable-model-invocation`, `skilloverrides`,
`triggering`, `~100 tokens`, `standalone`+`plugin`, `sampled sessions`),
`test_config_doctor_respects_global_personal_scope` (`deliberately global`, `keep them in
sync`, `within the same scope`), and `test_config_doctor_has_skill_reorg_lens` all still pass
because the reorganize section is untouched and the new section adds only.

- [ ] **Step 5: Commit**

```bash
git add skills/recommend-actions/prompts/config_doctor.md skills/recommend-actions/scripts/test_prompts.py
git commit -m "feat(config-doctor): profile-management lens — prioritized cleanup, team-vs-personal, always-on bloat"
```

---

### Task 4: `action_synthesizer.md` — let the alpha reach do_now/consider

**Files:**
- Modify: `skills/recommend-actions/prompts/action_synthesizer.md` (step 4, lines 18–22)
- Test: `skills/recommend-actions/scripts/test_prompts.py` (extend `test_synthesizer_balances_families_in_priority`)

**Interfaces:**
- Consumes: nothing new.
- Produces: prioritization guidance that makes high-tax cleanup and high-adoption acquire eligible for `do_now`/`consider`.

- [ ] **Step 1: Extend the failing test**

In `skills/recommend-actions/scripts/test_prompts.py`, **replace** `test_synthesizer_balances_families_in_priority` with:

```python
def test_synthesizer_balances_families_in_priority():
    text = _read("action_synthesizer")
    low = text.lower()
    assert "crowd out" in low
    assert "acquire" in low
    # high always-on bloat trims and strong adoption finds are do_now/consider eligible
    assert "bloat" in low
    assert "adoption" in low
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py::test_synthesizer_balances_families_in_priority -v`
Expected: FAIL (`bloat`/`adoption` not yet present).

- [ ] **Step 3: Edit step 4**

In `prompts/action_synthesizer.md`, in step 4, replace the sentence:

```
a high-impact `acquire` (a missing
   skill / MCP) or a skill **reorganization/cleanup** belongs in `do_now` just as much
   as a memory capture.
```

with:

```
a high-impact `acquire` (a missing skill / MCP,
   especially one with a real **adoption** signal) or a skill **reorganization/cleanup**
   (including a large always-on **bloat** trim) belongs in `do_now` just as much as a memory
   capture.
```

- [ ] **Step 4: Run the full prompt test suite**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py -v`
Expected: PASS (extended test green; everything else unchanged).

- [ ] **Step 5: Commit**

```bash
git add skills/recommend-actions/prompts/action_synthesizer.md skills/recommend-actions/scripts/test_prompts.py
git commit -m "feat(synthesizer): make high-adoption acquire and always-on-bloat trims do_now-eligible"
```

---

### Task 5: Regenerate cadel-mono-repo to verify (runtime step)

Not a code/test task — a guided runtime verification after Tasks 1–4 are merged and
`python -m pytest scripts/` is green. It requires the consent gate + a live web lookup (the
acquire survey needs network), so drive it interactively, do not script it silently. Because
the acquire lane is cached per profile (14-day TTL), force a fresh scout (allow the live
lookup) so the enriched survey actually runs.

- [ ] **Step 1: Confirm the suite is green**

Run: `cd skills/recommend-actions && python -m pytest scripts/ -q` → all pass.

- [ ] **Step 2: Regenerate**

Re-run the recommend-actions pipeline from the working copy for `/Volumes/Sources/cadel-mono-repo` with the live lookup allowed (the same manual orchestration used on 2026-06-26: load_profile → 4 specialists with the updated prompts → synthesizer → render).

- [ ] **Step 3: Verify the gaps closed**

Confirm in the regenerated report: the acquire lane surfaces **more than one** candidate, each citing a real adoption signal (e.g. Postgres MCP Pro / Sentry / FastAPI-MCP for this stack), with CLI-redundant ones (GitHub/Docker/Filesystem/Git) absent; and config now surfaces a **prioritized unused-cleanup** set (team-vs-personal levers) plus an **always-on bloat** trim targeting the 11.6KB repo `CLAUDE.md` / 15.6KB `MEMORY.md` — promoted out of FYI where warranted.

---

## Self-Review

**1. Spec coverage**
- `reference/sources.md` (sources + levers, re-verify caveat) → Task 1. ✔
- capability_scout adoption survey + adoption-signal requirement → Task 2 (Steps 4). ✔
- capability_scout CLI-vs-MCP recalibration (drop token cost; MCP deferred-cheap; don't suppress leverageful MCP) → Task 2 (Step 3). ✔
- config_doctor unused-cleanup lens (skill_usage ranking, team-vs-personal, verified levers) → Task 3. ✔
- config_doctor always-on bloat targeting + MCP de-emphasis → Task 3. ✔
- Keep cross-scope-duplicate guardrail → untouched in config_doctor; asserted green in Task 3 Step 4. ✔
- synthesizer prioritization tweak → Task 4. ✔
- Tests for each, LLM-free → Tasks 1–4. ✔
- Regenerate verification → Task 5. ✔
- No sensor/script/schema change → confirmed (only prompts, one reference, one test file). ✔

**2. Placeholder scan:** none — every step shows the exact text/code and location.

**3. Type consistency:** the cited path string is `reference/sources.md` verbatim in Tasks 1–3 and in the tests; the asserted strings (`disable-model-invocation`, `skillOverrides`, `settings.local.json`, `PulseMCP`/`Glama`, `200 lines`, `deferred by default`, `minimal context impact`, `visibility, not adoption`, `team-shared`, `skill_usage`, `always_on.sources`, `structured/programmatic access`, `simplicity`) each appear verbatim in the prose the same task inserts. Task 2 replaces `test_capability_scout_is_cli_first` (which asserted the now-removed `token cost`) so no test contradicts the new copy.

## Execution Handoff

Per the user's earlier choice, **stop here for approval** — present this plan and do not begin implementation until the user approves and chooses an execution mode.
