# ClaudeCoach Report Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild both ClaudeCoach reports (`profile.html`, `actions.html`) on one editorial-product design system so they read as a single, professional product.

**Architecture:** `skills/_shared/coach_theme.py` grows from a thin theme into a full component kit (masthead, hero, section, signal grid, weight bars, stat grid, evidence, callout, priority lane, action card, footer) carrying one token set + one CSS block lifted from the approved mockup. `visualize.py` and `render.py` become thin data-mappers that feed those components. Output stays self-contained HTML with inline CSS, no build step.

**Tech Stack:** Python 3 stdlib (`html`, `json`, `os`, `sys`, `webbrowser`), pytest. Google Fonts (Inter + Fraunces + IBM Plex Mono) with system fallback. No new deps.

## Global Constraints

- **Visual source of truth:** `docs/superpowers/specs/2026-06-16-claudecoach-report-redesign.mockup.html`. Task 1 lifts its `<style>` block verbatim into `coach_theme.STYLE`. Component functions must emit markup whose classes match that CSS exactly.
- **Tokens (already in the mockup CSS):** surfaces `--bg:#faf8f5 --surface:#fff --surface-2:#f5f2ec --inset:#f7f4ee`; ink `--ink:#1b1a17 --ink-2:#565049 --ink-3:#928b80`; lines `--line:#ece7dc --line-2:#ddd6c7`; `--accent:#bd4d2a --accent-deep:#9c3f22 --positive:#3c6b56`; families `--c-acquire:#3a6ea5 --c-config:#b5852f --c-author:#7d5ba6 --c-behavior:#3c6b56`; fonts `--sans:Inter --serif:Fraunces --mono:'IBM Plex Mono'`. Serif only for `h1`, section `h2`, big numbers.
- **`esc()` unchanged:** `html.escape("" if x is None else str(x))`.
- **Import seam unchanged:** each renderer prepends `../../_shared` to `sys.path` then `import coach_theme`. `skills/_shared/` stays SKILL.md-free.
- **Tests run per-skill-dir** (`cd skills/<skill> && python -m pytest scripts/ -q`; `_shared` from its own dir). NEVER `pytest skills/` (collides on duplicate basenames).
- **Transitional red (read carefully):** Task 1 changes `coach_theme`'s API/tokens, which breaks the *old* `visualize.py`/`render.py` and their tests until Tasks 2 and 3 rewrite them. Each task below states its EXACT in-scope test command. After Task 1, only `skills/_shared` must be green (profile-builder + recommend-actions suites are expected-red). After Task 2, `_shared` + profile-builder green (recommend-actions still expected-red). After Task 3, ALL green. Do not "fix" an out-of-scope suite inside an earlier task.
- **Preserved behaviors:** evidence = verbatim verified quotes with the junk/marker filter (`_quote`/`_usable_quote`); the collapsible unused-capabilities `<details>` (no `+N more` tail); the actions review-banner copy containing `/perform-actions` and "nothing has been changed"; the `capabilities {fetched_at}` meta text; the dangerous-URL-scheme guard (`SAFE_URL_SCHEMES`, drop `javascript:`); `None`→"" coercion; audience-neutral wording; pure `render_html`.
- **Packaging gate:** `python -m pytest tests/test_plugin_manifest.py -q` stays green.
- **Commit only with the user's go-ahead, on a feature branch (not `main`).**

---

### Task 1: Rebuild `coach_theme.py` as the component kit

**Files:**
- Rewrite: `skills/_shared/coach_theme.py`
- Rewrite: `skills/_shared/test_coach_theme.py`

**Interfaces — Produces (used by Tasks 2 & 3):**
- `esc(x) -> str`
- `page(title, masthead, body, footer) -> str` — full `<html>` shell; `masthead`/`footer` are full-width HTML, `body` goes inside one `.wrap`.
- `masthead(label, slug) -> str`
- `hero(kicker, title, standfirst, chips_html="") -> str`
- `chip(text, strong=None, dot=False) -> str`
- `section(num, title, body, eyebrow="") -> str` — returns `""` when `body` is falsy.
- `signal_grid(rows) -> str` — `rows`: list of `{"k","v","q"(opt),"d"(opt)}`.
- `weight_bars(items) -> str` — `items`: list of `{"label","weight"}` (weight clamped 0–1).
- `stat_grid(stats) -> str` — `stats`: list of `(number_str, caption)`.
- `evidence(who, quote) -> str`
- `impact_figure(value, caption) -> str`
- `callout(body_html, icon="📋") -> str`
- `priority_lane(label, kind, count) -> str` — `kind` ∈ `{"now","consider","fyi"}`.
- `action_card(title, family, effort, rationale_html, *, impact_html="", source_html="", evidence_html="", apply_kind="", apply_preview="") -> str`
- `footer(model_line, disclaimer) -> str`

- [ ] **Step 1: Write the failing tests** — replace `skills/_shared/test_coach_theme.py` with:

```python
"""Tests for the ClaudeCoach editorial-product component kit. Pure strings, no I/O."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coach_theme as ct  # noqa: E402


def test_esc_coerces_none_and_escapes():
    assert ct.esc(None) == ""
    assert ct.esc("<b>&") == "&lt;b&gt;&amp;"


def test_page_shell_carries_tokens_and_fonts():
    html = ct.page("T", "<header>m</header>", "<p>b</p>", "<footer>f</footer>")
    assert html.startswith("<!DOCTYPE html>")
    assert "<title>T</title>" in html and "</html>" in html
    assert "--accent:#bd4d2a" in html          # new token
    assert "Inter" in html and "Fraunces" in html
    assert '<div class="wrap"><p>b</p></div>' in html
    assert "<header>m</header>" in html and "<footer>f</footer>" in html


def test_masthead_has_wordmark_and_crumb():
    m = ct.masthead("profile", "-Volumes-x")
    assert "ClaudeCoach" in m and "/ profile" in m
    assert "Profile" in m                        # label.title() in the crumb
    assert "<code>-Volumes-x</code>" in m


def test_hero_structure_and_escaping():
    h = ct.hero("KICK", "Title <x>", "Lead.", ct.chip("c", strong="9"))
    assert 'class="kicker">KICK<' in h
    assert "<h1>Title &lt;x&gt;</h1>" in h
    assert "Lead." in h and 'class="chiprow">' in h and "<b>9</b>" in h


def test_section_empty_body_returns_blank():
    assert ct.section("01", "X", "") == ""
    s = ct.section("01", "How you work", "<p>x</p>", eyebrow="signals")
    assert '<span class="num">01</span>' in s and "<h2>How you work</h2>" in s
    assert "signals" in s and "<p>x</p>" in s


def test_signal_grid_renders_rows():
    g = ct.signal_grid([{"k": "Prompting", "v": "Directive and clear", "q": "do X"}])
    assert 'class="sigs"' in g and 'class="k">Prompting<' in g
    assert "Directive and clear" in g and 'class="q">do X<' in g


def test_weight_bars_clamp_and_label():
    b = ct.weight_bars([{"label": "Bugs", "weight": 0.93},
                        {"label": "Over", "weight": 2.0},
                        {"label": "Under", "weight": -1}])
    assert "width:93%" in b and "Bugs" in b
    assert "width:100%" in b                      # clamped high
    assert "width:0%" in b                        # clamped low
    assert ">.93<" in b                           # ".NN" label


def test_stat_grid():
    s = ct.stat_grid([("6,764", "tokens"), ("8", "hooks")])
    assert 'class="n">6,764<' in s and "tokens" in s and 'class="n">8<' in s


def test_evidence_and_impact_figure():
    assert 'class="who">session:a<' in ct.evidence("session:a", "hi")
    fig = ct.impact_figure("2", "re-explains avoided")
    assert "<b>2</b>" in fig and "re-explains avoided" in fig


def test_callout_holds_trusted_html():
    c = ct.callout("<b>review</b> then <code>/perform-actions</code>")
    assert 'class="callout"' in c and "/perform-actions" in c


def test_priority_lane_kind_classes():
    assert 'class="pri now"' in ct.priority_lane("Do now", "now", "3 actions")
    assert 'class="pri consider"' in ct.priority_lane("Consider", "consider", "")
    assert 'class="pri fyi"' in ct.priority_lane("FYI", "fyi", "1 action")


def test_action_card_family_color_and_drawer():
    a = ct.action_card("Install X", "acquire", "low",
                       "Because reasons.",
                       impact_html=ct.impact_figure("2", "avoided"),
                       source_html='verified · <a href="https://ex.com">src</a>',
                       evidence_html=ct.evidence("sig", "q"),
                       apply_kind="run_command", apply_preview="/plugin install x")
    assert 'class="acard"' in a and "<h3>Install X</h3>" in a
    assert "var(--c-acquire)" in a                 # family dot color
    assert "low effort" in a
    assert "Apply — run_command" in a and "/plugin install x" in a


def test_footer():
    f = ct.footer("Read by Haiku. ", "nondeterministic.")
    assert "ClaudeCoach" in f and "nondeterministic." in f
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/_shared && python -m pytest test_coach_theme.py -q`
Expected: FAIL — new functions/tokens not present yet (old module has `page(title, body)` etc.).

- [ ] **Step 3: Rewrite `skills/_shared/coach_theme.py`**

First set `STYLE` and `FONT_LINKS`, then the functions. For `STYLE`, copy the entire contents **between** `<style>` and `</style>` in `docs/superpowers/specs/2026-06-16-claudecoach-report-redesign.mockup.html` into the triple-quoted `STYLE` string, then append the two rules below (the appended `.sig .v` deliberately overrides the mockup's serif one — real signal values are sentences, not one-word levels, and read better in sans; later same-specificity rule wins):

```
.pri.fyi{background:var(--surface-2);color:var(--ink-3)}
.sig .v{font-family:var(--sans);font-size:.95rem;font-weight:500;color:var(--ink);letter-spacing:0;margin:3px 0 0}
```

Full module:

```python
#!/usr/bin/env python3
"""Shared editorial-product component kit for ClaudeCoach reports (profile.html and
actions.html). One token set, one CSS block (lifted from the approved mockup), and
the components both renderers compose. Pure string helpers, no I/O.

Consumers:  sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "..", "..", "_shared")); import coach_theme
"""
import html

FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600'
    '&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">'
)

STYLE = """<PASTE the mockup's <style> contents here, then append the two rules above>"""


def esc(x):
    """HTML-escape, coercing None to '' so a missing field never renders as 'None'."""
    return html.escape("" if x is None else str(x))


def page(title, masthead, body, footer):
    """Full themed document. masthead/footer are full-width HTML; body sits in one .wrap."""
    return (
        '<!DOCTYPE html>\n'
        '<html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>{esc(title)}</title>\n{FONT_LINKS}\n'
        f'<style>{STYLE}</style></head>\n<body>\n'
        f'{masthead}<div class="wrap">{body}</div>{footer}</body></html>'
    )


def masthead(label, slug):
    return (f'<header class="mast"><div class="wrap">'
            f'<div class="brand"><span class="mark"></span><b>ClaudeCoach</b>'
            f'<span>/ {esc(label)}</span></div>'
            f'<div class="crumbs"><span class="here">{esc(str(label).title())}</span> · '
            f'<code>{esc(slug)}</code></div></div></header>')


def hero(kicker, title, standfirst, chips_html=""):
    cr = f'<div class="chiprow">{chips_html}</div>' if chips_html else ""
    return (f'<div class="hero"><div class="kicker">{esc(kicker)}</div>'
            f'<h1>{esc(title)}</h1>'
            f'<p class="standfirst">{esc(standfirst)}</p>{cr}</div>')


def chip(text, strong=None, dot=False):
    d = '<span class="dot"></span>' if dot else ""
    s = f'<b>{esc(strong)}</b> ' if strong not in (None, "") else ""
    return f'<span class="chip">{d}{s}{esc(text)}</span>'


def section(num, title, body, eyebrow=""):
    if not body:
        return ""
    eb = f'<span class="eb">{esc(eyebrow)}</span>' if eyebrow else ""
    return (f'<section><div class="sec-head"><span class="num">{esc(num)}</span>'
            f'<h2>{esc(title)}</h2>{eb}</div>{body}</section>')


def signal_grid(rows):
    cells = []
    for r in rows or []:
        d = f'<div class="d">{esc(r["d"])}</div>' if r.get("d") else ""
        q = f'<div class="q">{esc(r["q"])}</div>' if r.get("q") else ""
        cells.append(f'<div class="sig"><div class="k">{esc(r.get("k"))}</div>'
                     f'<div class="v">{esc(r.get("v"))}</div>{d}{q}</div>')
    return f'<div class="sigs">{"".join(cells)}</div>' if cells else ""


def weight_bars(items):
    rows = []
    for it in items or []:
        try:
            w = max(0.0, min(1.0, float(it.get("weight", 0))))
        except (TypeError, ValueError):
            w = 0.0
        pct = f"{w:.2f}"
        pct = pct[1:] if pct.startswith("0.") else pct
        rows.append(f'<div class="bar-row"><span class="lab">{esc(it.get("label"))}</span>'
                    f'<div class="bar"><i style="width:{w * 100:.0f}%"></i></div>'
                    f'<span class="pct">{esc(pct)}</span></div>')
    return f'<div class="bars">{"".join(rows)}</div>' if rows else ""


def stat_grid(stats):
    cells = "".join(f'<div class="stat"><div class="n">{esc(n)}</div>'
                    f'<div class="c">{esc(c)}</div></div>' for n, c in (stats or []))
    return f'<div class="stats">{cells}</div>' if stats else ""


def evidence(who, quote):
    w = f'<span class="who">{esc(who)}</span>' if who else ""
    return f'<div class="ev">{w}{esc(quote)}</div>'


def impact_figure(value, caption):
    return f'<span class="impact"><b>{esc(value)}</b><span>{esc(caption)}</span></span>'


def callout(body_html, icon="📋"):
    return f'<div class="callout"><span class="ic">{esc(icon)}</span><p>{body_html}</p></div>'


def priority_lane(label, kind, count):
    cls = kind if kind in ("now", "consider", "fyi") else "fyi"
    cnt = f'<span class="count">{esc(count)}</span>' if count else ""
    return f'<div class="lane-head"><span class="pri {cls}">{esc(label)}</span>{cnt}</div>'


def action_card(title, family, effort, rationale_html, *, impact_html="",
                source_html="", evidence_html="", apply_kind="", apply_preview=""):
    fam = (f'<span class="tag fam"><span class="fdot" style="background:var(--c-{esc(family)})">'
           f'</span>{esc(family)}</span>')
    eff = f'<span class="tag">{esc(effort)} effort</span>' if effort else ""
    foot_bits = []
    if impact_html:
        foot_bits.append(impact_html)
    if source_html:
        foot_bits.append(f'<span class="src">{source_html}</span>')
    foot = f'<div class="foot">{"".join(foot_bits)}</div>' if foot_bits else ""
    drawer = ""
    if apply_kind or apply_preview:
        drawer = (f'<details class="apply"><summary>Apply — {esc(apply_kind)}</summary>'
                  f'<pre>{esc(apply_preview)}</pre></details>')
    return (f'<div class="acard"><div class="acard-top"><h3>{esc(title)}</h3>'
            f'<div class="tags">{fam}{eff}</div></div>'
            f'<p class="rat">{rationale_html}</p>{foot}{evidence_html}{drawer}</div>')


def footer(model_line, disclaimer):
    return (f'<footer><div class="wrap">'
            f'<b style="font-weight:600;color:var(--ink-2)">ClaudeCoach</b> &nbsp;·&nbsp; '
            f'{esc(model_line)}{esc(disclaimer)}</div></footer>')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/_shared && python -m pytest test_coach_theme.py -q`
Expected: PASS (13 passed).

- [ ] **Step 5: Confirm the packaging gate still passes**

Run: `cd /Volumes/Sources/claudecoach && python -m pytest tests/test_plugin_manifest.py -q`
Expected: PASS (3). (The profile-builder / recommend-actions suites are expected-red now — that is fixed in Tasks 2 & 3; do not touch them here.)

- [ ] **Step 6: Commit**

```bash
git add skills/_shared/coach_theme.py skills/_shared/test_coach_theme.py
git commit -m "feat(_shared): editorial-product component kit"
```

---

### Task 2: Rebuild `visualize.py` (profile.html) on the kit

**Files:**
- Rewrite: `skills/profile-builder/scripts/visualize.py` (the render layer; keep `build`/`main` I/O and the `_quote`/`_usable_quote`/`_evidence`-filter helpers from the prior pass)
- Rewrite the render tests in: `skills/profile-builder/scripts/test_visualize.py`

**Interfaces:**
- Consumes: `coach_theme.{esc,page,masthead,hero,chip,section,signal_grid,weight_bars,stat_grid,evidence,impact_figure,footer}` (Task 1).
- Produces: `render_html(project, user) -> str` (same signature).

- [ ] **Step 1: Rewrite the render tests** — replace the three render tests in `test_visualize.py` (keep the `PROJECT`/`USER` fixtures and the `_quote`/`_evidence` filter tests added in the prior pass) with:

```python
def test_render_uses_new_design_system():
    html = viz.render_html(PROJECT, USER)
    assert "--accent:#bd4d2a" in html        # new token -> kit in use
    assert "Inter" in html and "Fraunces" in html
    assert 'class="mast"' in html            # shared masthead
    assert "ClaudeCoach" in html             # wordmark / footer


def test_render_has_hero_and_sections():
    html = viz.render_html(PROJECT, USER)
    assert "A repository for building a Claude coaching plugin." in html  # standfirst (lead)
    assert "How you work" in html and 'class="sigs"' in html             # signal grid
    assert "directive" in html                                           # a signal value
    assert 'class="bars"' in html and "skill authoring" in html          # weight bars
    assert "watch it fail first" in html                                 # a verified quote
    assert "1,250" in html                                               # stat number
    assert "nondeterministic" in html.lower()                            # disclaimer in footer


def test_render_escapes_and_handles_empty():
    out = viz.render_html({"summary": "hi <script>alert(1)</script>"}, {})
    assert "<script>alert(1)" not in out and "&lt;script&gt;" in out
    assert "<html" in viz.render_html({}, {}) and "</html>" in viz.render_html({}, {})


def test_setup_section_collapsible_unused_no_more_tail():
    many = {**USER, "context_health": {**USER["context_health"],
            "unused_capabilities": [{"name": f"cap{i}", "kind": "skills",
                                     "source": "personal"} for i in range(15)]}}
    html = viz.render_html({}, many)
    assert "cap14" in html and "owned but unused" in html
    assert "+1 more" not in html and "+3 more" not in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/profile-builder && python -m pytest scripts/test_visualize.py -q`
Expected: FAIL — old `visualize.py` still calls the removed `coach_theme` API (`page(title, body)` etc.); imports/render break.

- [ ] **Step 3: Rewrite the render layer of `skills/profile-builder/scripts/visualize.py`**

Keep the module's imports (the `sys.path` insert + `import coach_theme`), `_esc = coach_theme.esc`, `_num`, and the prior-pass `_TRUNC_MARKER`/`_quote`/`_usable_quote` helpers. Replace everything from `_evidence` through `render_html` (and delete the old `_TEMPLATE`, `_weighted_tags`, `_section`, `_signals_block`, `_friction_block`, `_list_block`, `_strengths_gaps`, `_context_health`, `_SIGNAL_LABELS`) with:

```python
_SIGNALS = [("prompting", "Prompting"), ("planning", "Planning"),
            ("verification", "Verification"), ("steering", "Steering"), ("leverage", "Leverage")]


def _lead(text):
    """First sentence of a summary, for the hero standfirst."""
    t = (text or "").strip()
    for sep in (". ", "; "):
        if sep in t:
            return t.split(sep)[0].strip() + "."
    return t


def _ev_split(ev):
    """`session:<id> "quote"` -> (who, quote), or None if the quote is junk/empty/marker."""
    s = str(ev or "")
    q = _usable_quote(s)
    if not q:
        return None
    i = s.find('"')
    return (s[:i].strip() if i > 0 else "", q)


def _first_evidence(items):
    for it in items or []:
        wq = _ev_split(it)
        if wq:
            return coach_theme.evidence(wq[0], wq[1])
    return ""


def _signal_rows(user):
    sigs = user.get("behavioral_signals") or {}
    rows = []
    for key, label in _SIGNALS:
        s = sigs.get(key) or {}
        if not s.get("value"):
            continue
        q = ""
        for it in s.get("evidence") or []:
            wq = _ev_split(it)
            if wq:
                q = wq[1]
                break
        rows.append({"k": label, "v": s.get("value"), "q": q})
    return rows


def _friction_cards(user):
    cards = []
    for f in user.get("friction_signals") or []:
        conf = f.get("confidence")
        fig = (coach_theme.impact_figure("%d%%" % round(float(conf) * 100), "confidence")
               if isinstance(conf, (int, float)) else "")
        foot = '<div class="foot">%s</div>' % fig if fig else ""
        cards.append('<div class="card" style="margin-bottom:12px">'
                     '<p style="font-weight:500">%s</p>%s%s</div>'
                     % (_esc(f.get("pattern")), foot, _first_evidence(f.get("evidence"))))
    return "".join(cards)


def _sg_list(items, label_key, with_why=False):
    lis = []
    for it in items or []:
        why = ('<span class="d">%s</span>' % _esc(it.get("rationale"))) if with_why else ""
        lis.append('<li style="margin-bottom:12px"><b>%s</b>%s%s</li>'
                   % (_esc(it.get(label_key) or it.get("need")), why,
                      _first_evidence(it.get("evidence"))))
    return "<ul style='list-style:none;padding:0;margin:0'>%s</ul>" % "".join(lis) if lis else ""


def _strengths_gaps(user):
    s = _sg_list(user.get("strengths"), "area")
    g = _sg_list(user.get("gaps"), "area", with_why=True)
    if not s and not g:
        return ""
    cols = []
    if s:
        cols.append('<div class="card"><h3 class="minor">Strengths</h3>%s</div>' % s)
    if g:
        cols.append('<div class="card"><h3 class="minor">Candidate gaps — signals, not advice</h3>%s</div>' % g)
    return '<div class="grid2">%s</div>' % "".join(cols)


def _setup(user):
    ch = user.get("context_health") or {}
    if not ch:
        return ""
    ao = ch.get("always_on") or {}
    hooks = ch.get("hooks") or []
    dups = ch.get("duplicate_capabilities") or []
    unused = ch.get("unused_capabilities") or []
    mcp = ch.get("mcp_footprint") or {}
    htot = sum(h.get("count", 0) for h in hooks)
    grid = coach_theme.stat_grid([
        (_num(ao.get("est_tokens", 0)), "tokens load every session"),
        ("%d" % htot, "hook%s firing" % ("" if htot == 1 else "s")),
        ("%d" % (mcp.get("servers", 0) or 0), "MCP server%s" % ("" if (mcp.get("servers", 0) or 0) == 1 else "s")),
        ("%d" % len(unused), "capabilities unused here"),
    ])
    notes = ["Duplicate <b>%s</b> across %s" % (_esc(d.get("name")),
             _esc(" · ".join(d.get("sources", [])))) for d in dups]
    note_html = ("<ul class='plainlist' style='margin-top:14px;list-style:none;padding:0'>%s</ul>"
                 % "".join("<li>%s</li>" % n for n in notes)) if notes else ""
    unused_html = ""
    if unused:
        names = "".join("<li>%s</li>" % _esc(u.get("name")) for u in unused)
        unused_html = ('<details class="unused"><summary>%d capabilities owned but unused in '
                       'the sampled sessions</summary><ul class="plainlist" '
                       "style='list-style:none;padding:0;margin-top:8px'>%s</ul></details>"
                       % (len(unused), names))
    return ('<div class="card">%s%s%s'
            '<p style="font-size:12px;color:var(--ink-3);font-style:italic;margin-top:12px">'
            'Raw signals only — collected for a coach to act on, not recommendations from here.'
            "</p></div>") % (grid, note_html, unused_html)


def render_html(project, user):
    project = project or {}
    user = user or {}
    prov = project.get("provenance") or user.get("provenance") or {}
    work = project.get("work_type")
    title = ("%s work" % work.replace("-", " ").title()) if work else "How you work with Claude"
    slug = (project.get("project") or {}).get("slug") or ""
    gen = (project.get("generated_at") or user.get("generated_at") or "")[:10]

    chips = []
    if prov.get("sessions_sampled") is not None:
        chips.append(coach_theme.chip("of %s sessions read" % _num(prov.get("sessions_total", "?")),
                                      strong=_num(prov.get("sessions_sampled")), dot=True))
    if prov.get("quotes_verified") is not None:
        chips.append(coach_theme.chip("quotes verified", strong=_num(prov.get("quotes_verified"))))
        if prov.get("quotes_dropped"):
            chips.append(coach_theme.chip("unverifiable, dropped", strong=_num(prov.get("quotes_dropped"))))
    if gen:
        chips.append(coach_theme.chip("generated %s" % gen))

    body = [
        coach_theme.hero("Your Claude profile", title, _lead(project.get("summary")), "".join(chips)),
        coach_theme.section("01", "How you work", coach_theme.signal_grid(_signal_rows(user)),
                            eyebrow="behavioral signals"),
        coach_theme.section("02", "What the work is", coach_theme.weight_bars(
            [{"label": a.get("name"), "weight": a.get("weight")} for a in project.get("task_archetypes") or []]),
            eyebrow="task patterns, by weight"),
        coach_theme.section("03", "Where work snagged", _friction_cards(user), eyebrow="friction signals"),
        coach_theme.section("04", "Strengths & gaps", _strengths_gaps(user), eyebrow="a two-sided read"),
        coach_theme.section("05", "Your Claude setup", _setup(user), eyebrow="context-health signals"),
    ]

    models = prov.get("models") or {}
    model_line = ("Read by %s, synthesized by %s · " % (
        _esc(models.get("per_session", "?")), _esc(models.get("synthesis", "?")))) if models else ""
    disclaimer = (project.get("disclaimer") or user.get("disclaimer")
                  or "evidence-verified but nondeterministic.")
    return coach_theme.page(
        "%s — ClaudeCoach" % title,
        coach_theme.masthead("profile", slug),
        "".join(b for b in body if b),
        coach_theme.footer(model_line, disclaimer),
    )
```

- [ ] **Step 4: Run the profile-builder suite to verify pass**

Run: `cd skills/profile-builder && python -m pytest scripts/ -q`
Expected: PASS (all — incl. the retained `_quote`/`_evidence` filter tests). (recommend-actions is still expected-red until Task 3.)

- [ ] **Step 5: Smoke-render the real profile (optional, no-fail if dir absent)**

Run: `cd skills/profile-builder && python scripts/visualize.py ~/.claude/profiles/-Volumes-Sources-cadel-mono-repo`
Expected: writes/opens `profile.html` with the masthead, signal grid, weight bars, and full evidence quotes.

- [ ] **Step 6: Commit**

```bash
git add skills/profile-builder/scripts/visualize.py skills/profile-builder/scripts/test_visualize.py
git commit -m "feat(profile-builder): rebuild profile.html on the editorial-product kit"
```

---

### Task 3: Rebuild `render.py` (actions.html) on the kit

**Files:**
- Rewrite: `skills/recommend-actions/scripts/render.py` (the HTML layer; keep `group_by_priority`, `render_console`, `BANNER_TEXT`/`BANNER_HTML`, `SAFE_URL_SCHEMES`, `main`)
- Rewrite the HTML tests in: `skills/recommend-actions/scripts/test_render.py`

**Interfaces:**
- Consumes: `coach_theme.{esc,page,masthead,hero,chip,section,callout,priority_lane,action_card,impact_figure,evidence,footer}`.
- Produces: `render_html(doc) -> str`.

- [ ] **Step 1: Rewrite the HTML tests** — keep `DOC`, `test_group_by_priority`, `test_console_*`, `test_cli_writes_html`; replace the HTML-asserting tests with:

```python
def test_html_uses_new_design_system():
    html = render.render_html(DOC)
    assert "--accent:#bd4d2a" in html and "Inter" in html and "Fraunces" in html
    assert 'class="mast"' in html and "ClaudeCoach" in html


def test_html_has_lanes_cards_and_banner():
    html = render.render_html(DOC)
    assert 'class="pri now"' in html and "Do now" in html          # priority lane
    assert 'class="acard"' in html                                  # action card
    assert "var(--c-config)" in html or "var(--c-acquire)" in html  # family dot
    assert "Capture your test command" in html
    assert "the test command is pytest -q" in html                  # evidence quote
    assert "built_at 2026-06-10" in html                            # source freshness
    assert "nothing has been changed" in html and "/perform-actions" in html  # callout
    assert "capabilities 2026-06-10" in html                        # meta text preserved
    assert "Considered but not recommended" in html


def test_html_escapes_and_handles_empty():
    safe = render.render_html({**DOC, "actions": [
        {**DOC["actions"][0], "title": "<script>x</script>"}]})
    assert "<script>x</script>" not in safe
    assert "No actions" in render.render_html({**DOC, "actions": [], "not_recommended": []})


def test_html_drops_dangerous_url_scheme():
    doc = {**DOC, "actions": [{**DOC["actions"][1],
        "source": {"kind": "live_web", "ref": "", "url": "javascript:alert(1)", "freshness": ""}}]}
    assert "javascript:alert(1)" not in render.render_html(doc)


def test_impact_value_none_is_not_literal_none():
    doc = {**DOC, "actions": [{**DOC["actions"][0],
        "impact_estimate": {"kind": "tokens_saved", "value": None, "basis": "b"}}]}
    assert "None tokens_saved" not in render.render_html(doc)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_render.py -q`
Expected: FAIL — old `render_html` uses the removed `coach_theme.page(title, body)` / `section` signatures; render breaks.

- [ ] **Step 3: Rewrite the HTML layer of `skills/recommend-actions/scripts/render.py`**

Keep imports, `PRIORITIES`, `PRIORITY_LABEL`, `SAFE_URL_SCHEMES`, `BANNER_HTML`, `BANNER_TEXT`, `_esc`, `group_by_priority`, `_evidence_lines`, `render_console`, `main`. Add a `LANE_KIND` map. Replace `_card` and `render_html` with:

```python
LANE_KIND = {"do_now": "now", "consider": "consider", "fyi": "fyi"}


def _card(a):
    src = a.get("source", {})
    parts = []
    if src.get("freshness"):
        parts.append(_esc(src.get("freshness")))
    u = src.get("url") or ""
    if u.startswith(SAFE_URL_SCHEMES):
        parts.append(f'<a href="{_esc(u)}">source</a>')
    source_html = " · ".join(parts)
    imp = a.get("impact_estimate", {})
    impact_html = (coach_theme.impact_figure(imp.get("value"),
                   f'{_esc(imp.get("kind",""))} · {_esc(imp.get("basis",""))}')
                   if imp.get("kind") not in (None, "qualitative") else "")
    ev = ""
    for x in a.get("evidence", []):
        if x.get("quote"):
            ev = coach_theme.evidence(x.get("signal", ""), x.get("quote"))
            break
    apply_b = a.get("apply", {})
    return coach_theme.action_card(
        a.get("title", ""), a.get("family", ""), a.get("effort", ""),
        _esc(a.get("rationale", "")),
        impact_html=impact_html, source_html=source_html, evidence_html=ev,
        apply_kind=apply_b.get("kind", ""), apply_preview=apply_b.get("preview", ""))


def render_html(doc):
    g = group_by_priority(doc.get("actions", []))
    pr = doc.get("profile_ref", {})
    idx = doc.get("indexes", {})
    slug = doc.get("project_slug", "")
    chips = "".join([
        coach_theme.chip("profile %s" % _esc(pr.get("generated_at", "?"))),
        coach_theme.chip("sessions sampled", strong=_esc(pr.get("sessions_sampled", "?"))),
        coach_theme.chip("network used %s" % doc.get("consent", {}).get("network_used")),
        coach_theme.chip("capabilities %s" % _esc(idx.get("capabilities_fetched_at", "?"))),
    ])
    blocks = [
        coach_theme.hero("ClaudeCoach · recommendations", "What would make Claude work better here",
                         "Evidence-cited, opt-in actions drawn from your profile.", chips),
        coach_theme.callout(BANNER_HTML),
    ]
    any_action = False
    for p in PRIORITIES:
        if not g[p]:
            continue
        any_action = True
        n = len(g[p])
        blocks.append(coach_theme.priority_lane(
            PRIORITY_LABEL[p], LANE_KIND[p], "%d action%s" % (n, "" if n == 1 else "s")))
        blocks.append("".join(_card(a) for a in g[p]))
    if not any_action:
        blocks.append("<p>No actions — your setup looks well tuned for this project.</p>")
    nr = doc.get("not_recommended", [])
    nr_items = ("".join('<li style="margin-bottom:8px;color:var(--ink-2)">%s — %s</li>'
                        % (_esc(i.get("considered", "")), _esc(i.get("why_dropped", ""))) for i in nr)
                if nr else "<li>none</li>")
    blocks.append(coach_theme.section(
        "·", "Considered but not recommended",
        "<ul style='list-style:none;padding:0;font-size:13.5px'>%s</ul>" % nr_items))
    return coach_theme.page(
        "Recommendations — ClaudeCoach",
        coach_theme.masthead("recommendations", slug),
        "".join(blocks),
        coach_theme.footer("", _esc(doc.get("disclaimer", ""))))
```

- [ ] **Step 4: Run the recommend-actions suite to verify pass**

Run: `cd skills/recommend-actions && python -m pytest scripts/ -q`
Expected: PASS (all — console banner tests, CLI test, the new HTML tests).

- [ ] **Step 5: Smoke-render the real actions (optional, no-fail if dir absent)**

Run: `cd skills/recommend-actions && python scripts/render.py ~/.claude/profiles/-Volumes-Sources-cadel-mono-repo/actions.json --no-open`
Expected: writes `actions.html` with masthead, priority lanes, family-dot action cards, and the review callout.

- [ ] **Step 6: Commit**

```bash
git add skills/recommend-actions/scripts/render.py skills/recommend-actions/scripts/test_render.py
git commit -m "feat(recommend-actions): rebuild actions.html on the editorial-product kit"
```

---

## Final verification

- [ ] All suites + manifest green (the transitional-red window is now closed):
  ```bash
  cd /Volumes/Sources/claudecoach
  (cd skills/_shared && python -m pytest . -q)
  (cd skills/profile-builder && python -m pytest scripts/ -q)
  (cd skills/recommend-actions && python -m pytest scripts/ -q)
  python -m pytest tests/test_plugin_manifest.py -q
  ```
- [ ] Re-render both reports for `~/.claude/profiles/-Volumes-Sources-cadel-mono-repo` and eyeball them side by side: identical masthead/hero/footer, one type & color system, profile = signal-grid + weight-bars + stats, actions = priority lanes + family-dot cards + callout.

## Self-Review (done while writing)

- **Spec coverage:** masthead/hero/footer chrome → Task 1 + used in 2/3; type/space/token system → Task 1 STYLE; signal grid / weight bars / stat grid → Task 1 + Task 2; priority lanes / action cards / family dots / callout / impact figure → Task 1 + Task 3; preserved guards (URL, None-coercion, banner copy, capabilities meta, evidence filter, collapsible unused) → asserted in Task 2/3 tests. All mapped.
- **Placeholder scan:** the one external reference (`STYLE` = the mockup's `<style>` block) points at a committed file with exact delimiters — not a placeholder. All Python is complete.
- **Type consistency:** `page(title, masthead, body, footer)`, `section(num, title, body, eyebrow="")`, `signal_grid(rows)`, `weight_bars(items)`, `action_card(title, family, effort, rationale_html, *, …)`, `priority_lane(label, kind, count)` defined in Task 1 and called with matching shapes in Tasks 2 & 3.
- **Known data note (deviation from mockup):** the mockup showed one-word signal "levels" (Directive / Up-front); the profile JSON only carries the full `value` sentence, so the signal card renders that sentence (styled via the appended `.sig .v` sans override). Crisp one-word levels would need a synthesis-prompt change — out of scope here.
