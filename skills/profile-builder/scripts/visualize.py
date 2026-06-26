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
        foot = '<div class="foot" style="margin-top:12px">%s</div>' % fig if fig else ""
        cards.append('<div class="card" style="margin-bottom:12px">'
                     '<p style="font-weight:500">%s</p>%s%s</div>'
                     % (_esc(f.get("pattern")), foot, _first_evidence(f.get("evidence"))))
    return "".join(cards)


def _sg_list(items, label_key, with_why=False):
    lis = []
    for it in items or []:
        why = ('<div class="d" style="margin-top:4px">%s</div>' % _esc(it.get("rationale"))) if with_why else ""
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
            eyebrow="task patterns · share of sampled work"),
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
