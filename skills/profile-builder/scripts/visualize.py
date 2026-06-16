#!/usr/bin/env python3
"""Render a persisted profile (project.profile.json + user.profile.json) into one
self-contained, human-friendly HTML page and open it in the default browser.

Built to be read by ANY audience — engineer or accountant — so it leads with
plain-English summaries and shows evidence as quotes, not jargon. `render_html`
is pure (dicts -> HTML string) and unit-tested; `build`/`main` do the I/O.

Usage:
  python3 visualize.py <profiles-dir>        # e.g. ~/.claude/profiles/<slug>
"""
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


def _weighted_tags(items):
    out = []
    for it in items or []:
        name = _esc(it.get("name"))
        w = it.get("weight")
        try:
            w = float(w)
        except (TypeError, ValueError):
            w = 0.5
        # weight -> visual weight (size + ink)
        size = 0.82 + 0.5 * max(0.0, min(1.0, w))
        op = 0.55 + 0.45 * max(0.0, min(1.0, w))
        out.append('<span class="wtag" style="font-size:%.2frem;opacity:%.2f">%s</span>'
                   % (size, op, name))
    return '<div class="tags">%s</div>' % "".join(out) if out else ""


def _section(title, eyebrow, body, idx):
    return coach_theme.section(title, body, eyebrow=eyebrow, idx=idx)


# --- the page -----------------------------------------------------------------

_SIGNAL_LABELS = [
    ("prompting", "Prompting", "How they phrase requests"),
    ("planning", "Planning", "Forethought before acting"),
    ("verification", "Verification", "How they check the result"),
    ("steering", "Steering", "How they direct Claude"),
    ("leverage", "Leverage", "Outcome per unit of effort"),
]


def _signals_block(user):
    sigs = user.get("behavioral_signals") or {}
    cards = []
    for key, label, blurb in _SIGNAL_LABELS:
        s = sigs.get(key) or {}
        val = s.get("value")
        if not val:
            continue
        cards.append(
            '<div class="sig">'
            '<span class="sig-k">%s</span>'
            '<span class="sig-v">%s</span>'
            '<span class="sig-b">%s</span>%s</div>'
            % (_esc(label), _esc(val), _esc(blurb), _evidence(s.get("evidence"), 1)))
    return '<div class="sig-grid">%s</div>' % "".join(cards) if cards else ""


def _friction_block(user):
    fr = user.get("friction_signals") or []
    cards = []
    for f in fr:
        conf = f.get("confidence")
        conf_s = (' <span class="conf">confidence %d%%</span>' % round(float(conf) * 100)
                  if isinstance(conf, (int, float)) else "")
        cards.append('<div class="friction reveal-inline"><p class="fr-p">%s%s</p>%s</div>'
                     % (_esc(f.get("pattern")), conf_s, _evidence(f.get("evidence"), 1)))
    return '<div class="stack">%s</div>' % "".join(cards) if cards else ""


def _list_block(items, key, render):
    items = items or []
    if not items:
        return ""
    return '<ul class="plainlist">%s</ul>' % "".join("<li>%s</li>" % render(i) for i in items)


def _strengths_gaps(user):
    strengths = user.get("strengths") or []
    gaps = user.get("gaps") or []
    if not strengths and not gaps:
        return ""
    s_html = "".join(
        '<li><b>%s</b>%s</li>' % (_esc(s.get("area")), _evidence(s.get("evidence"), 1))
        for s in strengths)
    g_html = "".join(
        '<li><b>%s</b><span class="why">%s</span>%s</li>'
        % (_esc(g.get("area") or g.get("need")), _esc(g.get("rationale")),
           _evidence(g.get("evidence"), 1))
        for g in gaps)
    cols = []
    if s_html:
        cols.append('<div class="col"><h3 class="good">Strengths</h3><ul class="rich">%s</ul></div>' % s_html)
    if g_html:
        cols.append('<div class="col"><h3 class="watch">Candidate gaps '
                    '<span class="hint">signals for a coach, not advice</span></h3>'
                    '<ul class="rich">%s</ul></div>' % g_html)
    return '<div class="twocol">%s</div>' % "".join(cols)


def _context_health(user):
    ch = user.get("context_health") or {}
    if not ch:
        return ""
    ao = ch.get("always_on") or {}
    hooks = ch.get("hooks") or []
    dups = ch.get("duplicate_capabilities") or []
    overlaps = ch.get("overlapping_capabilities") or []
    unused = ch.get("unused_capabilities") or []
    mcp = ch.get("mcp_footprint") or {}
    hook_total = sum(h.get("count", 0) for h in hooks)
    stats = [
        ("%s" % _num(ao.get("est_tokens", 0)), "tokens load every session"),
        ("%d" % hook_total, "hook%s firing" % ("" if hook_total == 1 else "s")),
        ("%d" % (mcp.get("servers", 0) or 0), "MCP servers"),
        ("%d" % len(unused), "capabilities never used here"),
    ]
    stat_html = "".join('<div class="stat"><span class="num">%s</span><span class="cap">%s</span></div>'
                        % (n, _esc(c)) for n, c in stats)
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


def render_html(project, user):
    project = project or {}
    user = user or {}
    prov = project.get("provenance") or user.get("provenance") or {}
    work = project.get("work_type")
    title = ("%s work" % work.replace("-", " ").title()) if work else "How you work with Claude"
    slug = (project.get("project") or {}).get("slug") or ""
    gen = project.get("generated_at") or user.get("generated_at") or ""

    models = prov.get("models") or {}
    chips = []
    if prov.get("sessions_sampled") is not None:
        chips.append("%s of %s sessions read" % (_num(prov.get("sessions_sampled")),
                                                 _num(prov.get("sessions_total", "?"))))
    if prov.get("quotes_verified") is not None:
        chips.append("%s quotes verified" % _num(prov.get("quotes_verified")))
        if prov.get("quotes_dropped"):
            chips.append("%s unverifiable, dropped" % _num(prov.get("quotes_dropped")))
    chip_html = "".join('<span class="chip">%s</span>' % _esc(c) for c in chips)

    # at-a-glance cards
    proj_tags = _weighted_tags(project.get("domains")) + _weighted_tags(project.get("tools_and_materials"))
    glance = (
        '<div class="twocol">'
        '<div class="card reveal" style="animation-delay:.05s"><p class="eyebrow">This project</p>'
        '<p class="lede">%s</p>%s</div>'
        '<div class="card reveal" style="animation-delay:.1s"><p class="eyebrow">How you work</p>'
        '<p class="lede">%s</p>%s</div></div>'
        % (_esc(project.get("summary")), proj_tags,
           _esc(user.get("summary")), _signals_block(user)))

    idx = 3
    sections = []
    work_body = _weighted_tags(project.get("task_archetypes"))
    sections.append(_section("What the work is", "task patterns Claude was used for", work_body, idx)); idx += 1
    sections.append(_section("Where work snagged", "friction signals", _friction_block(user), idx)); idx += 1
    sections.append(_section("Strengths & gaps", "two-sided read", _strengths_gaps(user), idx)); idx += 1
    sections.append(_section("Your Claude setup", "context-health signals", _context_health(user), idx)); idx += 1

    disclaimer = project.get("disclaimer") or user.get("disclaimer") or ""
    model_line = ""
    if models:
        model_line = "Read by %s · synthesized by %s. " % (
            _esc(models.get("per_session", "?")), _esc(models.get("synthesis", "?")))

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


def build(profiles_dir, open_browser=True):
    """Read the two profile JSONs from a dir, render, write profile.html, open it."""
    def _load(name):
        try:
            with open(os.path.join(profiles_dir, name), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}
    out = os.path.join(profiles_dir, "profile.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render_html(_load("project.profile.json"), _load("user.profile.json")))
    if open_browser:
        webbrowser.open("file://" + os.path.abspath(out))
    return out


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        sys.stderr.write("usage: visualize.py <profiles-dir>\n")
        return 2
    path = build(argv[0])
    sys.stdout.write(path + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
