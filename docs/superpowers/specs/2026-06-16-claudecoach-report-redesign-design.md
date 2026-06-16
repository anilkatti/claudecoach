# ClaudeCoach report redesign — editorial-product design system

**Status:** approved design (visual mockup approved), pre-plan
**Date:** 2026-06-16
**Visual source of truth:** `docs/superpowers/specs/2026-06-16-claudecoach-report-redesign.mockup.html`
(approved mockup — implementers lift its tokens/CSS verbatim)
**Changes:** `skills/_shared/coach_theme.py` (grows from a thin theme into a component
kit), `skills/profile-builder/scripts/visualize.py`, `skills/recommend-actions/scripts/render.py`
and their tests.

## Problem

`profile.html` and `actions.html` now share *tokens* (the warm theme from the prior
pass) but not a *layout system*: profile uses a magazine/editorial grid, actions uses
a stack of dense report cards. They read as two artifacts, not one product. Specific
defects (observed in the live renders):

- **Profile:** top-heavy 4.4rem serif title; wall-of-text summaries; signal cards cram
  a run-on sentence into the "value" slot (not scannable); weighted tag clouds read as
  random font-size jitter, not data.
- **Actions:** each card is a wall (long rationale + colliding impact/source spans +
  evidence list + apply drawer) with no internal hierarchy; `Do now`/`Consider`/`FYI`
  are flat `<h2>`s so urgency isn't encoded; metadata styling is inconsistent.
- **Cross-page:** different headers, different card anatomy, no shared product chrome
  (wordmark/masthead/footer), no shared type/space scale or data-viz language.

## Decision

Adopt one **editorial-product design system** — clean near-white surfaces, a disciplined
grid, a crisp sans (Inter) for all UI/data, a restrained serif (Fraunces) reserved for
display headings and big numbers, IBM Plex Mono for code/IDs, and a single warm accent.
Apply it to **both** pages via a shared component kit in `coach_theme.py`, and rework
each page's layout and content density. Direction and scope approved with the user
(editorial-product hybrid; full redesign).

## Design tokens (lift verbatim from the mockup)

```
surfaces   --bg:#faf8f5  --surface:#fff  --surface-2:#f5f2ec  --inset:#f7f4ee
ink        --ink:#1b1a17  --ink-2:#565049  --ink-3:#928b80
lines      --line:#ece7dc  --line-2:#ddd6c7
accent     --accent:#bd4d2a  --accent-deep:#9c3f22   positive --positive:#3c6b56
families   --c-acquire:#3a6ea5  --c-config:#b5852f  --c-author:#7d5ba6  --c-behavior:#3c6b56
type       --sans:Inter  --serif:Fraunces  --mono:'IBM Plex Mono'   base 15px / 1.55
radius     --r:12px  --r-sm:8px      shadow  --sh-sm, --sh (subtle, single elevation)
maxw       1000px content column
```

Serif is used **only** for `h1`, section `h2`, and big stat/figure numbers. Everything
else (labels, body, data, chips, code) is Inter or Mono.

## Architecture: `coach_theme.py` becomes the component kit

The renderers stay thin data-mappers; all visual structure lives in `coach_theme`. The
sensor→coach→executor separation, evidence-verified quotes, and audience-neutral wording
are unchanged — this is presentation only. Output stays **self-contained HTML with inline
CSS, no build step**.

```
  coach_theme.py  (kit — single source of truth)
  ├─ esc, FONT_LINKS (Inter+Fraunces+IBM Plex Mono), STYLE (the full token+component CSS)
  ├─ page(title, masthead, body, footer)         full <html> shell
  ├─ masthead(section_label, crumb)              sticky product bar: ◆ ClaudeCoach / <label> · <slug>
  ├─ hero(kicker, title, standfirst, chips=[])   kicker → serif title → standfirst → chip row
  ├─ chip(text, strong=None) / chips(list)
  ├─ section(num, title, eyebrow, body)          "01 · <serif title> · <eyebrow>"; empty body → ""
  ├─ signal_grid(rows)                           profile "how you work": label→level→detail→quote
  ├─ weight_bars(items)                          ranked label + clay bar + .NN  (replaces tag jitter)
  ├─ stat_grid(stats)                            big serif number + caption
  ├─ evidence(items)                             quote with a mono source label + left rule
  ├─ callout(body_html)                          the actions review banner
  ├─ priority_lane(label, kind, count)           Do now (solid) / Consider (outline) / FYI (muted) + count
  ├─ action_card(...)                            title + family dot-chip + effort chip + rationale
  │                                              + impact figure + evidence + Apply drawer
  └─ footer(model_line, disclaimer)              wordmark + provenance
             │                                            │
   visualize.py (profile.html)                 render.py (actions.html)
   maps profile JSON → masthead/hero/           maps actions.json → masthead/hero/
   signal_grid/weight_bars/stat_grid/           callout/priority_lane/action_card/
   card/evidence/section                        section/footer
```

**Import seam unchanged:** each renderer adds `../../_shared` to `sys.path` and
`import coach_theme` (already in place). `skills/_shared/` stays SKILL.md-free; the
`plugin validate --strict` gate must stay green.

## Page mapping

**profile.html** (`visualize.py`)
- masthead `profile · <slug>` + hero (kicker "Your Claude profile", title = work type,
  standfirst = project summary's lead sentence, chips = provenance: sessions read,
  quotes verified, dropped, generated date).
- §01 **How you work** → `signal_grid` (Prompting / Planning / Verification / Steering /
  Leverage: each = label → level → one-line detail → one verified quote).
- §02 **What the work is** → `weight_bars` over `task_archetypes` (and a second group for
  domains/tools if present), ranked by weight.
- §03 **Where work snagged** → friction `card`s, confidence shown as a small figure/meter.
- §04 **Strengths & gaps** → two-column `card`s with `evidence`.
- §05 **Your Claude setup** → `stat_grid` + duplicates list + the collapsible unused
  `<details>` (kept from the prior pass).
- footer.

**actions.html** (`render.py`)
- masthead `recommendations · <slug>` + hero + the meta line (profile date/stale/sessions/
  network/capabilities) rendered as chips.
- `callout` review banner (the `/perform-actions` next-step copy — unchanged text).
- For each non-empty priority: `priority_lane(label, kind, count)` then the `action_card`s.
- "Considered but not recommended" as a muted `section`.
- footer.

`action_card` anatomy: title; right-aligned family **dot-chip** (color per
`--c-{family}`) + effort chip; rationale (≤~72ch); a `foot` row with the **impact
figure** (serif number + caption, only when `impact_estimate.kind` ≠ qualitative/None)
and the source (built/verified date + verified link when a safe URL is present); an
`evidence` quote with a mono signal label; an `Apply — <kind>` drawer (mono `<pre>`).
The existing **dangerous-URL guard** (`SAFE_URL_SCHEMES`) and **None-coercion** are
preserved.

## Preserved behaviors / invariants

- Self-contained HTML, inline CSS, no build/runtime deps beyond Google Fonts (graceful
  system fallback when offline).
- `render_html(project, user)` / `render_html(doc)` stay pure (dict → str), unit-tested.
- Evidence = verbatim verified quotes (the prior `_quote`/`_evidence` junk/marker filter
  is retained); `+N more` stays a collapsible, not a raw tail.
- Audience-neutral wording; sensor→coach→executor separation; reversible/opt-in framing.
- Dangerous-URL scheme guard; `None`→"" coercion; the review-banner `/perform-actions`
  copy; the `capabilities {fetched_at}` meta text.

## Testing

LLM-free, per-skill-dir (`cd skills/<skill> && python -m pytest scripts/ -q`; never
`pytest skills/`). New/updated:
- `skills/_shared/test_coach_theme.py`: each new component renders expected structure
  (e.g. `masthead` emits the wordmark + crumb; `weight_bars` clamps width 0–100% and
  emits the `.NN` label; `priority_lane` emits the right `kind` class; `action_card`
  emits the family dot color + drops a `javascript:` URL; `section` still returns "" on
  empty body; `esc` unchanged).
- `test_visualize.py`: signal grid / weight bars / stat grid present; masthead+footer
  present; escaping intact; the retained evidence-filter cases still pass.
- `test_render.py`: priority lanes, family dot-chips, callout banner + `/perform-actions`,
  impact figure, `capabilities {fetched_at}`, dangerous-URL drop, empty-actions branch,
  None-coercion — all still hold against the new markup.

## Out of scope / non-goals

- No change to what profile-builder collects or what recommend-actions recommends (this
  is presentation only — the broadened scout/reorg/priority logic already shipped).
- No `perform-actions` HTML output.
- No JS interactivity beyond native `<details>`; no client framework; no build pipeline.
- No new data fields in the profile/actions JSON schemas.

## Risks

- **Three Google fonts** (Inter, Fraunces, IBM Plex Mono) add network weight; acceptable
  for a local report and they fall back to system fonts offline. No self-hosting.
- **Larger `STYLE`** in `coach_theme.py` — mitigated by keeping all CSS in the one shared
  module (still a single source of truth) and lifting it verbatim from the approved mockup.
