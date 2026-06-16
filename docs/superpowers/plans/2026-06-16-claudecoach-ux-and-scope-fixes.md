# ClaudeCoach UX & Scope Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify ClaudeCoach's HTML outputs onto one shared theme, fix the profile evidence-truncation bug, add a review banner + broaden recommendations, and clean up the worktree scope framing.

**Architecture:** A new `skills/_shared/coach_theme.py` becomes the single source of truth for the warm/serif page shell, tokens, and components; `visualize.py` (profile.html) and `render.py` (actions.html) both import it. The profile evidence-quote bug and the "setup" section polish live in `visualize.py`; the review banner and family-accent cards live in `render.py`; the worktree framing is a `profile-builder/SKILL.md` wording change; the broader-recommendations work is three `recommend-actions` prompt edits.

**Tech Stack:** Python 3 (stdlib only — `html`, `string`, `json`, `os`, `sys`, `webbrowser`), pytest. No new dependencies. HTML/CSS inline (no build step).

## Global Constraints

- **Tests run per-skill-dir, never repo-wide.** `python -m pytest skills/` collides on duplicate basenames (`test_integration.py`, `test_prompts.py` exist in two skills). Always `cd skills/<skill> && python -m pytest scripts/ -q`. The shared module's tests run from `skills/_shared/`.
- **Shared module import seam (verbatim in every consumer):**
  ```python
  import os, sys
  sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_shared"))
  import coach_theme
  ```
- **`skills/_shared/` must NOT contain a `SKILL.md`** — skill discovery is `skills/*/SKILL.md`; a SKILL.md there would register it as a fourth skill and break `tests/test_plugin_manifest.py::test_repo_ships_three_known_skills`.
- **Packaging gate:** after creating `skills/_shared/`, `python -m pytest tests/test_plugin_manifest.py -q` must stay green (it runs `claude plugin validate --strict`). If it fails on the extra dir, fall back to a **top-level `shared/`** and change the import seam to `"..", "..", "..", "shared"`.
- **`esc()` semantics (must match both current `_esc` copies):** `html.escape("" if x is None else str(x))`.
- **Aesthetic:** warm/light palette from the current `profile.html` (`--paper:#f5f0e8; --ink:#221f1b; --muted:#736a5e; --line:#e6ddcd; --accent:#c4562f; --accent2:#4d7359; --card:#fffefb`), Fraunces + Spline Sans.
- **Per repo convention, commit only with the user's go-ahead, on a feature branch (not `main`).** Commit steps below are the intended grouping; confirm before running them.
- **Invariants preserved:** sensor→coach→executor separation; collect-don't-judge; reversible/opt-in apply; evidence = verbatim verified quotes; audience-neutral language.

---

### Task 1: Shared theme module (`coach_theme.py`) + tests + packaging gate

**Files:**
- Create: `skills/_shared/coach_theme.py`
- Test: `skills/_shared/test_coach_theme.py`

**Interfaces:**
- Produces:
  - `coach_theme.esc(x) -> str` — `html.escape("" if x is None else str(x))`.
  - `coach_theme.FONT_LINKS: str`, `coach_theme.STYLE: str` (raw CSS, no `<style>` tags).
  - `coach_theme.page(title: str, body: str, *, lang: str = "en") -> str` — full `<!DOCTYPE html>…</html>` with head+fonts+`<style>`, body wrapped in `<div class="wrap">`.
  - `coach_theme.section(title: str, body: str, *, eyebrow: str = "", idx: int = 0) -> str` — `<section class="reveal">…</section>`; returns `""` when `body` is falsy.
  - `coach_theme.callout(body_html: str) -> str` — `<div class="callout">{body_html}</div>` (body_html is caller-trusted HTML).

- [ ] **Step 1: Write the failing test** — `skills/_shared/test_coach_theme.py`:

```python
"""Tests for the shared ClaudeCoach HTML theme. Pure string helpers, no I/O."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coach_theme as ct  # noqa: E402


def test_esc_coerces_none_and_escapes():
    assert ct.esc(None) == ""
    assert ct.esc("<b>&") == "&lt;b&gt;&amp;"
    assert ct.esc(12) == "12"


def test_page_is_wellformed_and_carries_tokens():
    html = ct.page("My Title", "<p>hello</p>")
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "<title>My Title</title>" in html
    assert '<div class="wrap"><p>hello</p></div>' in html
    assert "--paper:#f5f0e8" in html        # shared token present
    assert "Fraunces" in html               # shared font present


def test_page_escapes_title():
    html = ct.page("<script>x</script>", "")
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_section_renders_and_omits_empty():
    s = ct.section("Heading", "<p>body</p>", eyebrow="eyebrow text", idx=2)
    assert "<h2>Heading</h2>" in s
    assert "eyebrow text" in s
    assert "<p>body</p>" in s
    assert "animation-delay:0.10s" in s     # 0.05 * idx
    assert ct.section("Heading", "") == ""  # empty body -> no section


def test_callout_wraps_trusted_html():
    assert ct.callout("<b>hi</b>") == '<div class="callout"><b>hi</b></div>'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/_shared && python -m pytest test_coach_theme.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach_theme'`.

- [ ] **Step 3: Write `skills/_shared/coach_theme.py`**

```python
#!/usr/bin/env python3
"""Shared HTML theme for ClaudeCoach reports (profile-builder's profile.html and
recommend-actions' actions.html). One palette, one page scaffold, a few shared
components — so every ClaudeCoach output reads as one product. Pure string
helpers, no I/O.

Consumers add this dir to sys.path and import it:

    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "_shared"))
    import coach_theme
"""
import html

FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,900&family=Spline+Sans:wght@400;500;600&display=swap" rel="stylesheet">'
)

# Warm/serif base (lifted from profile-builder's original profile.html) plus the
# action-report components recommend-actions needs (cards, family accents, banner).
STYLE = """
:root{
  --paper:#f5f0e8; --ink:#221f1b; --muted:#736a5e; --line:#e6ddcd;
  --accent:#c4562f; --accent2:#4d7359; --card:#fffefb;
  --acquire:#3d6fb3; --config:#c4892f; --author:#8a5fbf; --behavior:#4d7359;
  --display:'Fraunces',Georgia,serif; --body:'Spline Sans',ui-sans-serif,system-ui,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);
  line-height:1.55;-webkit-font-smoothing:antialiased;
  background-image:radial-gradient(110% 60% at 80% -10%,#fbeede 0%,transparent 60%),
    radial-gradient(80% 50% at -10% 0%,#eef1e8 0%,transparent 55%);}
.wrap{max-width:920px;margin:0 auto;padding:clamp(28px,6vw,72px) clamp(20px,5vw,40px) 80px;}
.eyebrow{font:600 .72rem var(--body);letter-spacing:.18em;text-transform:uppercase;
  color:var(--accent);margin:0 0 .5rem;}
header.hero{border-bottom:2px solid var(--ink);padding-bottom:28px;margin-bottom:8px;}
h1{font:900 clamp(2.6rem,7vw,4.4rem) var(--display);line-height:.98;margin:.1em 0 .25em;
  letter-spacing:-.015em;}
.meta{color:var(--muted);font-size:.95rem;}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px;}
.chip{font-size:.78rem;background:#fff;border:1px solid var(--line);border-radius:999px;
  padding:5px 12px;color:var(--muted);}
section,.card{margin-top:34px;}
h2{font:600 1.7rem var(--display);margin:0 0 .6em;letter-spacing:-.01em;}
h2::before{content:"";display:inline-block;width:26px;height:3px;background:var(--accent);
  vertical-align:middle;margin-right:12px;transform:translateY(-5px);}
.twocol{display:grid;grid-template-columns:1fr 1fr;gap:22px;}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px 26px;
  box-shadow:0 1px 0 #fff inset,0 14px 30px -22px rgba(60,40,20,.5);}
.lede{font:500 1.12rem/1.5 var(--body);margin:.2em 0 1em;}
.tags{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:baseline;}
.wtag{font-weight:600;color:var(--ink);}
.wtag::before{content:"#";color:var(--accent);opacity:.5;}
.sig-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;}
.sig{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px;display:flex;
  flex-direction:column;gap:2px;}
.sig-k{font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
.sig-v{font:600 1.25rem var(--display);color:var(--accent2);}
.sig-b{font-size:.78rem;color:var(--muted);}
.stack{display:flex;flex-direction:column;gap:14px;}
.friction{background:var(--card);border-left:3px solid var(--accent);border-radius:0 12px 12px 0;
  padding:16px 20px;box-shadow:0 10px 26px -24px rgba(60,40,20,.6);}
.fr-p{margin:0;font-weight:500;}
.conf{font-size:.72rem;color:var(--muted);font-weight:400;}
.evidence{margin-top:10px;}
.evidence blockquote{margin:6px 0 0;padding-left:12px;border-left:2px solid var(--line);
  color:var(--muted);font-style:italic;font-size:.88rem;}
.col h3{font:600 1.15rem var(--display);margin:0 0 .5em;}
.col .good{color:var(--accent2);} .col .watch{color:var(--accent);}
.hint{font:400 .7rem var(--body);color:var(--muted);font-style:italic;letter-spacing:0;}
ul.rich{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:12px;}
ul.rich>li{background:#fff;border:1px solid var(--line);border-radius:12px;padding:13px 16px;}
ul.rich .why{display:block;color:var(--muted);font-size:.88rem;margin-top:3px;}
ul.plainlist{margin:.4em 0 0;padding-left:1.1em;color:var(--ink);}
ul.plainlist li{margin:.3em 0;}
.health{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px 26px;
  box-shadow:0 14px 30px -24px rgba(60,40,20,.5);}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:16px;margin-bottom:8px;}
.stat{text-align:center;border-right:1px solid var(--line);}
.stat:last-child{border-right:none;}
.stat .num{display:block;font:900 2rem var(--display);color:var(--accent);line-height:1;}
.stat .cap{display:block;font-size:.76rem;color:var(--muted);margin-top:4px;}
.micro{font-size:.78rem;color:var(--muted);font-style:italic;margin:.8em 0 0;}
details.unused{margin-top:10px;}
details.unused>summary{cursor:pointer;color:var(--accent);font-size:.85rem;font-weight:500;}
footer{margin-top:54px;padding-top:22px;border-top:1px solid var(--line);
  font-size:.82rem;color:var(--muted);}
/* --- action-report components (recommend-actions) --- */
.callout{background:#fff;border:1px solid var(--line);border-left:4px solid var(--accent);
  border-radius:0 14px 14px 0;padding:16px 20px;margin:22px 0 6px;
  box-shadow:0 10px 26px -24px rgba(60,40,20,.6);font-size:.96rem;}
.callout strong{color:var(--ink);} .callout code{background:#f3ecdf;border-radius:5px;padding:1px 5px;}
.card.action{margin-top:14px;border-left-width:3px;}
.card.action.acquire{border-left-color:var(--acquire);}
.card.action.config{border-left-color:var(--config);}
.card.action.author{border-left-color:var(--author);}
.card.action.behavior{border-left-color:var(--behavior);}
.card .t{font:600 1.05rem var(--body);}
.card .meta{color:var(--muted);font-weight:400;font-size:.8rem;margin-left:8px;}
.card .ev{color:var(--muted);font-size:.82rem;margin:.5em 0 0;padding-left:1.1em;}
.card .src,.card .impact{color:var(--accent2);font-size:.75rem;}
.card details>summary{cursor:pointer;color:var(--accent);font-size:.85rem;margin-top:8px;}
.card pre{background:#f3ecdf;border:1px solid var(--line);padding:10px;border-radius:8px;
  overflow:auto;font-size:.8rem;white-space:pre-wrap;}
a{color:var(--accent);}
.fine{color:var(--muted);font-size:.78rem;margin-top:10px;}
@media(max-width:680px){.twocol{grid-template-columns:1fr;}.stat{border-right:none;}}
.reveal{opacity:0;transform:translateY(14px);animation:rise .7s cubic-bezier(.2,.7,.2,1) forwards;}
@keyframes rise{to{opacity:1;transform:none;}}
@media(prefers-reduced-motion:reduce){.reveal{animation:none;opacity:1;transform:none;}}
"""


def esc(x):
    """HTML-escape, coercing None to '' so a missing field never renders as 'None'."""
    return html.escape("" if x is None else str(x))


def page(title, body, *, lang="en"):
    """Wrap pre-built body HTML in the full themed document."""
    return (
        '<!DOCTYPE html>\n'
        f'<html lang="{esc(lang)}"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{esc(title)}</title>\n'
        f'{FONT_LINKS}\n'
        f'<style>{STYLE}</style></head>\n'
        f'<body><div class="wrap">{body}</div></body></html>'
    )


def section(title, body, *, eyebrow="", idx=0):
    """A titled section with the staggered reveal animation. Empty body -> ''."""
    if not body:
        return ""
    eb = f'<p class="eyebrow">{esc(eyebrow)}</p>' if eyebrow else ""
    return (f'<section class="reveal" style="animation-delay:{0.05 * idx:.2f}s">{eb}'
            f'<h2>{esc(title)}</h2>{body}</section>')


def callout(body_html):
    """A prominent intro banner. body_html is caller-built, already-escaped HTML."""
    return f'<div class="callout">{body_html}</div>'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd skills/_shared && python -m pytest test_coach_theme.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Confirm `_shared` has no SKILL.md and the packaging gate is green**

Run: `cd /Volumes/Sources/claudecoach && ls skills/_shared/ && python -m pytest tests/test_plugin_manifest.py -q`
Expected: `coach_theme.py  test_coach_theme.py` (no `SKILL.md`); pytest PASS (3 passed). If `test_manifest_validates_strict` fails on the extra dir, apply the Global-Constraints fallback (move to top-level `shared/`, change the import seam to `"..","..","..","shared"`) and re-run.

- [ ] **Step 6: Commit**

```bash
git add skills/_shared/coach_theme.py skills/_shared/test_coach_theme.py
git commit -m "feat(_shared): add shared coach_theme HTML module"
```

---

### Task 2: Fix profile evidence truncation (`_quote`/`_evidence`)

Confirmed bug: `_quote` splits on `"` and returns `parts[1]`, so a quote containing an inner `"` is cut at the first inner quote (real output: `**There's no `, `So `). Fix = first-quote-to-last-quote extraction + drop junk/marker quotes.

**Files:**
- Modify: `skills/profile-builder/scripts/visualize.py:32-47` (`_quote`, `_evidence`)
- Test: `skills/profile-builder/scripts/test_visualize.py`

**Interfaces:**
- Produces: `_quote(ev) -> str` (text between first and last `"`, else the string unchanged); `_evidence(items, limit=3) -> str` (renders only usable quotes; drops empty / <3-char / truncation-marker quotes).

- [ ] **Step 1: Write the failing tests** — append to `skills/profile-builder/scripts/test_visualize.py`:

```python
def test_quote_keeps_embedded_quotes():
    # The real bug: a quote containing an inner " was cut at the first inner quote.
    assert viz._quote('session:a "He said "hi" and left"') == 'He said "hi" and left'


def test_quote_passthrough_when_no_quotes():
    raw = "context_health.duplicate_capabilities frontend-design [personal, plugin]"
    assert viz._quote(raw) == raw


def test_evidence_drops_junk_and_marker_quotes():
    items = [
        'session:a "So "',                                   # 2 chars after strip -> drop
        'session:b "[…profile-builder truncated 900 chars…]"',  # marker -> drop
        'session:c "a real, illustrative quote"',            # keep
    ]
    out = viz._evidence(items)
    assert "a real, illustrative quote" in out
    assert ">So <" not in out
    assert "truncated" not in out


def test_evidence_empty_when_all_junk():
    assert viz._evidence(['session:a "So "']) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/profile-builder && python -m pytest scripts/test_visualize.py -q`
Expected: FAIL — `test_quote_keeps_embedded_quotes` returns `'He said '`; junk tests still render `So`.

- [ ] **Step 3: Replace `_quote`/`_evidence`** in `skills/profile-builder/scripts/visualize.py` (the block at lines 32–47) with:

```python
_TRUNC_MARKER = "profile-builder truncated"


def _quote(ev):
    """An evidence string like `session:abc "quote"` -> the quoted text. Uses the
    first and last double-quote so a quote with INNER quotes survives intact."""
    s = str(ev or "")
    i, j = s.find('"'), s.rfind('"')
    if i != -1 and j > i:
        return s[i + 1:j]
    return s


def _usable_quote(ev):
    """The extracted quote if it's a real illustration, else '' — drops empties,
    sub-3-char fragments, and any leaked profile-builder truncation marker."""
    q = _quote(ev).strip()
    if len(q) < 3 or _TRUNC_MARKER in q:
        return ""
    return q


def _evidence(items, limit=3):
    quotes = []
    for it in items or []:
        q = _usable_quote(it)
        if q:
            quotes.append(q)
        if len(quotes) >= limit:
            break
    if not quotes:
        return ""
    blocks = "".join('<blockquote>%s</blockquote>' % _esc(q) for q in quotes)
    return '<div class="evidence">%s</div>' % blocks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd skills/profile-builder && python -m pytest scripts/test_visualize.py -q`
Expected: PASS (all, incl. the existing `test_render_html_includes_key_sections` which still finds `watch it fail first`).

- [ ] **Step 5: Commit**

```bash
git add skills/profile-builder/scripts/visualize.py skills/profile-builder/scripts/test_visualize.py
git commit -m "fix(profile-builder): keep inner quotes, drop junk/marker evidence"
```

---

### Task 3: Refactor `visualize.py` onto `coach_theme` + polish the setup section

**Files:**
- Modify: `skills/profile-builder/scripts/visualize.py` (imports + `_esc`, `_section`, `_context_health`, `render_html`, remove `_TEMPLATE`)
- Test: `skills/profile-builder/scripts/test_visualize.py`

**Interfaces:**
- Consumes: `coach_theme.esc`, `coach_theme.page`, `coach_theme.section` (Task 1).
- Produces: `render_html(project, user) -> str` (same signature; now built via `coach_theme.page`); `_context_health(user) -> str` (no `+N more` tail — full list inside a `<details class="unused">`).

- [ ] **Step 1: Write the failing tests** — append to `test_visualize.py`:

```python
def test_render_uses_shared_theme():
    html = viz.render_html(PROJECT, USER)
    # --acquire exists ONLY in coach_theme.STYLE, not the old inline _TEMPLATE,
    # so this fails before the refactor and passes after.
    assert "--acquire:#3d6fb3" in html
    assert "Fraunces" in html


def test_setup_section_has_no_plus_more_tail():
    many = {**USER, "context_health": {**USER["context_health"],
            "unused_capabilities": [{"name": f"cap{i}", "kind": "skills",
                                     "source": "personal"} for i in range(15)]}}
    html = viz.render_html({}, many)
    assert "more" not in html.split("capabilities owned but unused")[1][:40]  # no "+N more"
    assert "cap14" in html                # full list rendered (in the collapsible details)
    assert "owned but unused" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/profile-builder && python -m pytest scripts/test_visualize.py -q`
Expected: FAIL — `test_render_uses_shared_theme` fails (`--acquire` token only exists in `coach_theme.STYLE`, not the old `_TEMPLATE`); `test_setup_section_has_no_plus_more_tail` fails (current code emits `+N more`).

- [ ] **Step 3a: Swap imports + helpers.** In `visualize.py`, change the import block (lines 12–17) and the two tiny helpers:

Replace `import html` / `import string` usage. New top-of-file (after the docstring):

```python
import json
import os
import sys
import webbrowser

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_shared"))
import coach_theme  # noqa: E402

# --- tiny render helpers ------------------------------------------------------

_esc = coach_theme.esc


def _num(n):
    try:
        return "{:,}".format(int(n))
    except (TypeError, ValueError):
        return _esc(n)
```

(`import html` and `import string` are now unused — remove them. `_esc`'s old `def` is replaced by the alias above.)

- [ ] **Step 3b: Delegate `_section` to the shared component.** Replace `_section` (lines 67–72) with:

```python
def _section(title, eyebrow, body, idx):
    return coach_theme.section(title, body, eyebrow=eyebrow, idx=idx)
```

- [ ] **Step 3c: Polish `_context_health`.** Replace the `notes`/`note_html`/return block (lines 164–179) with:

```python
    notes = []
    for d in dups:
        notes.append("Duplicate <b>%s</b> across %s"
                     % (_esc(d.get("name")), _esc(" · ".join(d.get("sources", [])))))
    for o in overlaps:
        notes.append("Overlapping: <b>%s</b> &amp; <b>%s</b> (%s)"
                     % (_esc(o.get("a")), _esc(o.get("b")), _esc(o.get("overlap"))))
    note_html = ("<ul class='plainlist'>%s</ul>" % "".join("<li>%s</li>" % n for n in notes)
                 if notes else "")
    unused_html = ""
    if unused:
        names = "".join("<li>%s</li>" % _esc(u.get("name")) for u in unused)
        unused_html = ('<details class="unused"><summary>%d capabilities owned but unused '
                       'in the sampled sessions</summary><ul class="plainlist">%s</ul></details>'
                       % (len(unused), names))
    return ('<div class="health"><div class="stats">%s</div>%s%s'
            '<p class="micro">Raw signals only — collected for a coach to act on, not '
            'recommendations from here.</p></div>') % (stat_html, note_html, unused_html)
```

- [ ] **Step 3d: Build the page via `coach_theme.page`.** Replace the `render_html` return (lines 227–236) with the hero/footer assembly and drop `_TEMPLATE` (delete lines 239–327):

```python
    hero = (
        '<header class="hero reveal">'
        '<p class="eyebrow">Your Claude profile</p>'
        '<h1>%s</h1>'
        '<p class="meta">%s &nbsp;·&nbsp; generated %s</p>'
        '<div class="chips">%s</div></header>'
        % (_esc(title), _esc(slug), _esc(gen[:10] if gen else ""), chip_html))
    footer = ('<footer>%s%s This profile reflects the current project only; '
              'a cross-project view comes later.</footer>'
              % (model_line, _esc(disclaimer)))
    body = hero + glance + "".join(s for s in sections if s) + footer
    return coach_theme.page("%s — Claude profile" % title, body)
```

- [ ] **Step 4: Run the full profile-builder suite to verify pass**

Run: `cd skills/profile-builder && python -m pytest scripts/ -q`
Expected: PASS (all). Existing assertions (`developer tooling`, `re-explains the git push…`, `frontend-design`, `directive`, `watch it fail first`, `1,250`, `nondeterministic`, escape test, empty-profile test) still hold; new shared-theme + setup tests pass.

- [ ] **Step 5: Smoke-render the real profile and eyeball it**

Run: `cd skills/profile-builder && python scripts/visualize.py ~/.claude/profiles/-Volumes-Sources-cadel-mono-repo`
Expected: opens `profile.html`; the factual-claim-discipline strength now shows a full quote (no `**There's no `), and the setup section shows a "N capabilities owned but unused…" expandable list (no `+41 more`).

- [ ] **Step 6: Commit**

```bash
git add skills/profile-builder/scripts/visualize.py skills/profile-builder/scripts/test_visualize.py
git commit -m "refactor(profile-builder): render via shared coach_theme; tidy setup section"
```

---

### Task 4: Refactor `render.py` onto `coach_theme` + review banner

**Files:**
- Modify: `skills/recommend-actions/scripts/render.py` (imports, `_esc`, `_card`, `render_console`, `render_html`)
- Test: `skills/recommend-actions/scripts/test_render.py`

**Interfaces:**
- Consumes: `coach_theme.esc`, `coach_theme.page`, `coach_theme.section`, `coach_theme.callout`.
- Produces: `render_html(doc) -> str` (themed page, with review banner); `render_console(doc) -> str` (banner line prepended); `BANNER_HTML: str`, `BANNER_TEXT: str` module constants.

- [ ] **Step 1: Write the failing tests** — append to `skills/recommend-actions/scripts/test_render.py`:

```python
def test_html_has_review_banner_and_next_step():
    html = render.render_html(DOC)
    assert "review" in html.lower()
    assert "nothing has been changed" in html.lower()
    assert "/perform-actions" in html


def test_console_has_review_banner():
    txt = render.render_console(DOC)
    assert "/perform-actions" in txt
    assert "review" in txt.lower()


def test_html_uses_shared_theme():
    html = render.render_html(DOC)
    assert "--paper:#f5f0e8" in html       # shared token -> shared module in use
    assert "Fraunces" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_render.py -q`
Expected: FAIL — no banner, no `/perform-actions`, dark theme has no `--paper`.

- [ ] **Step 3a: Imports + banner constants + `_esc`.** Replace `render.py` lines 5–19 (the imports through `_esc`) with:

```python
import argparse
import json
import os
import sys
import webbrowser

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_shared"))
import coach_theme  # noqa: E402

PRIORITIES = ["do_now", "consider", "fyi"]
PRIORITY_LABEL = {"do_now": "Do now", "consider": "Consider", "fyi": "FYI"}
SAFE_URL_SCHEMES = ("http://", "https://")

BANNER_HTML = ("<strong>These are potential actions for you to review — nothing has been "
               "changed yet.</strong> Next, run <code>/perform-actions</code>; Claude will "
               "walk you through each one so you can pick and choose which to apply.")
BANNER_TEXT = ("These are potential actions for you to review — nothing has been changed yet. "
               "Next, run /perform-actions; Claude will walk you through each one so you can "
               "pick and choose which to apply.")

_esc = coach_theme.esc
```

(`import html` is removed — `_esc` now comes from `coach_theme`.)

- [ ] **Step 3b: Prepend the banner in `render_console`.** Change the `lines = [...]` initializer (lines 39–42) so the banner is the first block:

```python
    lines = [BANNER_TEXT, "",
             f'Recommendations for {doc.get("project_slug","")}',
             f'  profile {doc.get("profile_ref",{}).get("generated_at","?")} '
             f'(stale={doc.get("profile_ref",{}).get("stale")})  '
             f'network_used={doc.get("consent",{}).get("network_used")}', ""]
```

- [ ] **Step 3c: Theme the card.** Replace `_card` (lines 65–84) — add the `action` class so it picks up the shared family accent + tighter spacing:

```python
def _card(a):
    src = a.get("source", {})
    fresh = f'<span class="src">{_esc(src.get("freshness",""))}</span>' if src.get("freshness") else ""
    u = src.get("url") or ""
    url = f' · <a href="{_esc(u)}">source</a>' if u.startswith(SAFE_URL_SCHEMES) else ""
    imp = a.get("impact_estimate", {})
    impact = (f'<span class="impact">{_esc(imp.get("value"))} {_esc(imp.get("kind",""))}'
              f' — {_esc(imp.get("basis",""))}</span>' if imp.get("kind") not in (None, "qualitative") else "")
    ev = "".join(f'<li><b>{_esc(x.get("signal",""))}</b>: {_esc(x.get("quote",""))}</li>'
                 for x in a.get("evidence", []))
    apply_b = a.get("apply", {})
    preview = _esc(apply_b.get("preview", ""))
    return f"""
    <div class="card action {_esc(a.get('family',''))}">
      <div class="t">{_esc(a.get('title',''))}
        <span class="meta">{_esc(a.get('family',''))} · {_esc(a.get('effort',''))} effort{url}</span></div>
      <p>{_esc(a.get('rationale',''))} {impact} {fresh}</p>
      <ul class="ev">{ev}</ul>
      <details><summary>Apply ({_esc(apply_b.get('kind',''))})</summary><pre>{preview}</pre></details>
    </div>"""
```

- [ ] **Step 3d: Rebuild `render_html` via `coach_theme.page`.** Replace `render_html` (lines 87–123) with:

```python
def render_html(doc):
    g = group_by_priority(doc.get("actions", []))
    pr = doc.get("profile_ref", {})
    idx = doc.get("indexes", {})
    hero = (
        '<header class="hero reveal">'
        '<p class="eyebrow">ClaudeCoach · recommendations</p>'
        '<h1>What would make Claude work better here</h1>'
        f'<p class="meta">{_esc(doc.get("project_slug",""))}</p></header>')
    intro = coach_theme.callout(BANNER_HTML)
    meta = (f'<p class="fine">profile {_esc(pr.get("generated_at","?"))} · '
            f'stale={pr.get("stale")} · sessions sampled {_esc(pr.get("sessions_sampled","?"))} · '
            f'network used {doc.get("consent",{}).get("network_used")} · '
            f'capabilities {_esc(idx.get("capabilities_fetched_at","?"))}</p>')
    body_sections = []
    for i, p in enumerate(PRIORITIES):
        if not g[p]:
            continue
        body_sections.append(coach_theme.section(
            PRIORITY_LABEL[p], "".join(_card(a) for a in g[p]), idx=i))
    if not any(g[p] for p in PRIORITIES):
        body_sections.append("<p>No actions — your setup looks well tuned for this project.</p>")
    nr = doc.get("not_recommended", [])
    nr_items = ("".join(f'<li>{_esc(i.get("considered",""))} — '
                        f'{_esc(i.get("why_dropped",""))}</li>' for i in nr)
                if nr else "<li>none</li>")
    nr_section = coach_theme.section("Considered but not recommended", f"<ul>{nr_items}</ul>")
    footer = f'<footer>{_esc(doc.get("disclaimer",""))}</footer>'
    body = hero + intro + meta + "".join(body_sections) + nr_section + footer
    return coach_theme.page(f"recommend-actions — {doc.get('project_slug','')}", body)
```

- [ ] **Step 4: Run the full recommend-actions suite to verify pass**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_render.py -q`
Expected: PASS (all). Existing assertions still hold: `Do now`/`Consider` (from `section`), `Capture your test command`, `the test command is pytest -q`, `built_at 2026-06-10`, `Considered but not recommended`, `nondeterministic`, `No actions`, dangerous-URL drop, `None`-coercion, `capabilities 2026-06-10`.

- [ ] **Step 5: Commit**

```bash
git add skills/recommend-actions/scripts/render.py skills/recommend-actions/scripts/test_render.py
git commit -m "feat(recommend-actions): themed actions.html + review banner"
```

---

### Task 5: Worktree scope framing in `profile-builder/SKILL.md` (issue 1)

Doc change. No collection-code change — `discover()` already folds worktrees. The goal: stop Claude improvising a "main repo vs worktree" prompt, and frame the real axis.

**Files:**
- Modify: `skills/profile-builder/SKILL.md` (insert a "Scope" note after Step 0's blockquote, line 31)

- [ ] **Step 1: Insert the scope note.** After the Step 0 consent blockquote (the line ending `…Haiku/Opus subagents. Proceed?"`, line 31) and before `## Step 0.5`, add:

```markdown

**Scope — this project (worktrees auto-included).** Profile **this project**;
`sessions.py discover()` automatically folds in every git worktree of the repo, so
the sample is the project's whole history. **Do not ask the user to choose between
the main repo and a worktree** — fold them silently, then after Step 1 tell the user
which worktree roots were included (the `report["worktrees"]` list). A cross-project
**"all projects together"** view is coming in a later version; if the user asks for
it, say it's not available yet and offer to proceed with this project.
```

- [ ] **Step 2: Verify the wording is present and the old framing is absent**

Run:
```bash
cd /Volumes/Sources/claudecoach
grep -n "Do not ask the user to choose" skills/profile-builder/SKILL.md
grep -n "all projects together" skills/profile-builder/SKILL.md
grep -ni "main repo or\|current worktree" skills/profile-builder/SKILL.md || echo "OK: no repo-vs-worktree choice phrasing"
```
Expected: first two grep hits print; third prints `OK: no repo-vs-worktree choice phrasing`.

- [ ] **Step 3: Confirm the skill's plumbing tests still pass (unchanged, sanity)**

Run: `cd skills/profile-builder && python -m pytest scripts/ -q`
Expected: PASS (no code touched; guards against an accidental edit).

- [ ] **Step 4: Commit**

```bash
git add skills/profile-builder/SKILL.md
git commit -m "docs(profile-builder): fold worktrees silently; frame this-project vs all-projects"
```

---

### Task 6: Broaden recommendations — three `recommend-actions` prompt edits (issue 3)

**Files:**
- Modify: `skills/recommend-actions/prompts/capability_scout.md`, `prompts/config_doctor.md`, `prompts/action_synthesizer.md`
- Test: `skills/recommend-actions/scripts/test_prompts.py`

- [ ] **Step 1: Write the failing tests** — append to `skills/recommend-actions/scripts/test_prompts.py`:

```python
def test_capability_scout_surfaces_wellknown_options():
    text = _read("capability_scout")
    assert "well-known" in text.lower()
    assert "verify" in text.lower()                      # URL rail still present
    assert "never" in text.lower() and "invent" in text.lower()


def test_config_doctor_has_skill_reorg_lens():
    text = _read("config_doctor")
    assert "reorganize" in text.lower()
    assert "owned_capabilities" in text
    assert "archive" in text.lower()


def test_synthesizer_balances_families_in_priority():
    text = _read("action_synthesizer")
    assert "crowd out" in text.lower()
    assert "acquire" in text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py -q`
Expected: FAIL — the three new assertions (no `well-known`, no `reorganize`, no `crowd out` yet).

- [ ] **Step 3a: Broaden `capability_scout.md`.** Insert this section immediately before `## Evidence rule` (line 31):

```markdown
## Surface strong, well-known options — not only literal gap-fillers
Within the profile's scope, you may also recommend a **widely-used, well-known,
well-maintained** capability the person lacks even when no gap is spelled out — e.g.
an established skill / MCP / plugin for a high-weight `domain` or `task_archetype`
they work in repeatedly. The rails are unchanged: it must be **scoped to this
profile**, the person must **not already own it** (dedupe against `owned_capabilities`),
and you must **fetch and verify its URL** before emitting it — never an invented name
or an unverified URL. Prefer established, maintained options over obscure ones.
```

- [ ] **Step 3b: Add the reorg lens to `config_doctor.md`.** Change the intro line "Three kinds of action: **trim**, **fill**, **automate**." (line 4) to "Four kinds of action: **trim**, **fill**, **automate**, **reorganize**." Then append this bullet to the `## What to look for` list (after the `automate_hook` bullet, line 20):

```markdown
- **reorganize your skills** (`action_type: "trim"` or `"merge_sharpen"`, apply
  `archive`) — beyond exact duplicates, scan `owned_capabilities` for capabilities
  scattered across personal/repo/plugin scopes, broadly overlapping, or genuinely
  unused in the sample, and propose a **consolidation**: archive the redundant copy,
  keep the best-placed one, or merge overlapping ones into a single clear capability.
  Reversible archive, never delete; "unused" stays "unused in the sampled sessions."
```

- [ ] **Step 3c: Fix prioritization in `action_synthesizer.md`.** Replace step 4 (lines 17–18, the `**Prioritize**…→ do_now.` item) with:

```markdown
4. **Prioritize** into `do_now` / `consider` / `fyi` from impact × confidence, with
   `effort` shown (never hidden). Rank on genuine impact and **do not let one family
   (e.g. `capture_context`) crowd out the others**: a high-impact `acquire` (a missing
   skill / MCP) or a skill **reorganization/cleanup** belongs in `do_now` just as much
   as a memory capture. Surface the strongest few across families rather than filling
   `do_now` with one kind of action.
```

- [ ] **Step 4: Run the full prompts suite to verify pass**

Run: `cd skills/recommend-actions && python -m pytest scripts/test_prompts.py -q`
Expected: PASS (all). Existing `test_specialist_prompts_have_lane_placeholder_and_json_output`, `test_capability_scout_is_live_scoped_no_static_index`, and `test_synthesizer_prompt_has_candidates_and_actions_schema` still hold (placeholders, `untrusted`, `verify`, `invent`, `do_now`/`consider`/`fyi` all retained).

- [ ] **Step 5: Commit**

```bash
git add skills/recommend-actions/prompts/capability_scout.md skills/recommend-actions/prompts/config_doctor.md skills/recommend-actions/prompts/action_synthesizer.md skills/recommend-actions/scripts/test_prompts.py
git commit -m "feat(recommend-actions): broaden scout, add skill-reorg lens, balance priorities"
```

---

## Final verification

- [ ] Run each skill's suite + the shared + manifest tests:
  ```bash
  cd /Volumes/Sources/claudecoach
  (cd skills/_shared && python -m pytest . -q)
  (cd skills/profile-builder && python -m pytest scripts/ -q)
  (cd skills/recommend-actions && python -m pytest scripts/ -q)
  python -m pytest tests/test_plugin_manifest.py -q
  ```
  Expected: all PASS.
- [ ] Eyeball both reports side by side (same palette/fonts): `profile.html` and a re-rendered `actions.html` for `~/.claude/profiles/-Volumes-Sources-cadel-mono-repo`.

## Self-Review (done while writing)

- **Spec coverage:** issue 1 → Task 5; issue 2 → Tasks 2 (quote bug) + 3 (setup polish); issue 3 → Task 6; issue 4 → Tasks 1 + 3 + 4; issue 5 → Task 4. All five mapped.
- **Placeholder scan:** no TBD/TODO; every code step shows complete code; every test step shows real assertions and exact run commands with expected output.
- **Type/name consistency:** `coach_theme.{esc,page,section,callout,STYLE,FONT_LINKS}` defined in Task 1 and used with matching signatures in Tasks 3–4; `_quote`/`_evidence`/`_usable_quote` defined in Task 2 and preserved by Task 3; `BANNER_HTML`/`BANNER_TEXT` defined and used in Task 4. `section(title, body, *, eyebrow, idx)` keyword order consistent across consumers.
- **Known deviation from spec:** spec said "`pytest skills/` green"; corrected to per-skill-dir runs (repo-wide collection collides on duplicate basenames — pre-existing).
