#!/usr/bin/env python3
"""Render a persisted profile (project.profile.json + user.profile.json) into one
self-contained, human-friendly HTML page and open it in the default browser.

Built to be read by ANY audience — engineer or accountant — so it leads with
plain-English summaries and shows evidence as quotes, not jargon. `render_html`
is pure (dicts -> HTML string) and unit-tested; `build`/`main` do the I/O.

Usage:
  python3 visualize.py <profiles-dir>        # e.g. ~/.claude/profiles/<slug>
"""
import html
import json
import os
import string
import sys
import webbrowser

# --- tiny render helpers ------------------------------------------------------

def _esc(x):
    return html.escape(str(x if x is not None else ""))


def _num(n):
    try:
        return "{:,}".format(int(n))
    except (TypeError, ValueError):
        return _esc(n)


def _quote(ev):
    """An evidence string like `session:abc "quote"` -> just the quoted part if present."""
    s = str(ev or "")
    if '"' in s:
        parts = s.split('"')
        if len(parts) >= 3:
            return parts[1]
    return s


def _evidence(items, limit=3):
    items = [i for i in (items or []) if str(i).strip()][:limit]
    if not items:
        return ""
    quotes = "".join('<blockquote>%s</blockquote>' % _esc(_quote(i)) for i in items)
    return '<div class="evidence">%s</div>' % quotes


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
    if not body:
        return ""
    eb = '<p class="eyebrow">%s</p>' % _esc(eyebrow) if eyebrow else ""
    return ('<section class="reveal" style="animation-delay:%.2fs">%s'
            '<h2>%s</h2>%s</section>') % (0.05 * idx, eb, _esc(title), body)


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
        notes.append("Duplicate <b>%s</b> installed at: %s"
                     % (_esc(d.get("name")), _esc(", ".join(d.get("sources", [])))))
    for o in overlaps:
        notes.append("Overlapping descriptions: <b>%s</b> &amp; <b>%s</b> (%s)"
                     % (_esc(o.get("a")), _esc(o.get("b")), _esc(o.get("overlap"))))
    if unused:
        names = ", ".join(_esc(u.get("name")) for u in unused[:12])
        more = "" if len(unused) <= 12 else " +%d more" % (len(unused) - 12)
        notes.append("Owned but unused here: %s%s" % (names, more))
    note_html = ("<ul class='plainlist'>%s</ul>" % "".join("<li>%s</li>" % n for n in notes)
                 if notes else "")
    return ('<div class="health"><div class="stats">%s</div>%s'
            '<p class="micro">Raw signals only — collected for a coach to act on, not '
            'recommendations from here.</p></div>') % (stat_html, note_html)


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

    return string.Template(_TEMPLATE).safe_substitute({
        "title": _esc(title),
        "slug": _esc(slug),
        "gen": _esc(gen[:10] if gen else ""),
        "chips": chip_html,
        "glance": glance,
        "sections": "".join(s for s in sections if s),
        "model_line": model_line,
        "disclaimer": _esc(disclaimer),
    })


_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title} — Claude profile</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,900&family=Spline+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#f5f0e8; --ink:#221f1b; --muted:#736a5e; --line:#e6ddcd;
  --accent:#c4562f; --accent2:#4d7359; --card:#fffefb;
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
footer{margin-top:54px;padding-top:22px;border-top:1px solid var(--line);
  font-size:.82rem;color:var(--muted);}
@media(max-width:680px){.twocol{grid-template-columns:1fr;}.stat{border-right:none;}}
.reveal{opacity:0;transform:translateY(14px);animation:rise .7s cubic-bezier(.2,.7,.2,1) forwards;}
@keyframes rise{to{opacity:1;transform:none;}}
@media(prefers-reduced-motion:reduce){.reveal{animation:none;opacity:1;transform:none;}}
</style></head>
<body><div class="wrap">
<header class="hero reveal">
  <p class="eyebrow">Your Claude profile</p>
  <h1>${title}</h1>
  <p class="meta">${slug} &nbsp;·&nbsp; generated ${gen}</p>
  <div class="chips">${chips}</div>
</header>
${glance}
${sections}
<footer>${model_line}${disclaimer} This profile reflects the current project only;
a cross-project view comes later.</footer>
</div></body></html>
"""


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
