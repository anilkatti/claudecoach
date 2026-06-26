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

STYLE = """
:root{
  --bg:#faf8f5; --surface:#fff; --surface-2:#f5f2ec; --inset:#f7f4ee;
  --ink:#1b1a17; --ink-2:#565049; --ink-3:#928b80;
  --line:#ece7dc; --line-2:#ddd6c7;
  --accent:#bd4d2a; --accent-deep:#9c3f22; --positive:#3c6b56;
  --c-acquire:#3a6ea5; --c-config:#b5852f; --c-author:#7d5ba6; --c-behavior:#3c6b56;
  --sans:'Inter',ui-sans-serif,system-ui,sans-serif;
  --serif:'Fraunces',Georgia,serif; --mono:'IBM Plex Mono',ui-monospace,monospace;
  --r:12px; --r-sm:8px;
  --sh-sm:0 1px 2px rgba(28,26,23,.05);
  --sh:0 1px 2px rgba(28,26,23,.04),0 14px 30px -20px rgba(60,40,20,.30);
  --maxw:1000px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.55;
  -webkit-font-smoothing:antialiased;letter-spacing:-0.006em}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 28px}

/* ---- masthead (shared product chrome) ---- */
.mast{position:sticky;top:0;z-index:5;background:rgba(250,248,245,.86);backdrop-filter:saturate(1.4) blur(8px);
  border-bottom:1px solid var(--line)}
.mast .wrap{display:flex;align-items:center;justify-content:space-between;height:54px}
.brand{display:flex;align-items:center;gap:9px;font-weight:600;letter-spacing:-.01em}
.brand .mark{width:18px;height:18px;border-radius:5px;background:conic-gradient(from 210deg,var(--accent),#e08a4f,var(--accent));
  box-shadow:inset 0 0 0 1.5px rgba(255,255,255,.35)}
.brand b{font-weight:600} .brand span{color:var(--ink-3);font-weight:500}
.crumbs{font-size:13px;color:var(--ink-3);display:flex;gap:8px;align-items:center}
.crumbs .here{color:var(--ink);font-weight:500}
.crumbs code{font-family:var(--mono);font-size:12px;background:var(--surface-2);padding:2px 7px;border-radius:6px}

/* ---- hero ---- */
.hero{padding:56px 0 30px;border-bottom:1px solid var(--line)}
.kicker{font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--accent-deep)}
h1{font-family:var(--serif);font-weight:500;font-size:clamp(2.1rem,4.5vw,3rem);line-height:1.04;
  letter-spacing:-.02em;margin:.34em 0 .28em}
.standfirst{font-size:1.06rem;color:var(--ink-2);max-width:60ch}
.chiprow{display:flex;flex-wrap:wrap;gap:8px;margin-top:22px}
.chip{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;color:var(--ink-2);
  background:var(--surface);border:1px solid var(--line-2);border-radius:999px;padding:5px 12px}
.chip b{font-weight:600;color:var(--ink)}
.chip .dot{width:6px;height:6px;border-radius:50%;background:var(--accent)}

/* ---- section ---- */
section{padding:38px 0}
section + section{border-top:1px solid var(--line)}
.sec-head{display:flex;align-items:baseline;gap:14px;margin-bottom:22px}
.sec-head .num{font-family:var(--mono);font-size:12px;color:var(--accent);padding-top:3px}
.sec-head h2{font-family:var(--serif);font-weight:500;font-size:1.5rem;letter-spacing:-.015em}
.sec-head .eb{margin-left:auto;font-size:12px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.1em}

/* ---- cards / grids ---- */
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:22px 24px;box-shadow:var(--sh-sm)}
.card .lede{color:var(--ink-2);font-size:.96rem}
.card h3.minor{font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:12px}

/* signals grid */
.sigs{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.sig{background:var(--surface);padding:16px 18px}
.sig .k{font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)}
.sig .v{font-family:var(--serif);font-size:1.18rem;color:var(--ink);margin:3px 0 4px;letter-spacing:-.01em}
.sig .d{font-size:13px;color:var(--ink-2)}
.sig .q{font-size:12.5px;color:var(--ink-3);border-left:2px solid var(--line-2);padding-left:9px;margin-top:9px;font-style:italic}

/* weight bars */
.bars{display:flex;flex-direction:column;gap:11px}
.bar-row{display:grid;grid-template-columns:minmax(180px,260px) 1fr 34px;gap:14px;align-items:center}
.bar-row .lab{font-size:13.5px;font-weight:500}
.bar{height:7px;background:var(--surface-2);border-radius:999px;overflow:hidden}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--accent),#d9743f);border-radius:999px}
.bar-row .pct{font-family:var(--mono);font-size:12px;color:var(--ink-3);text-align:right}

/* ---- actions: priority lanes + action cards ---- */
.lane-head{display:flex;align-items:center;gap:11px;margin:6px 0 14px}
.pri{font-size:11.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:4px 11px;border-radius:999px}
.pri.now{background:var(--accent);color:#fff}
.pri.consider{background:transparent;color:var(--accent-deep);border:1.5px solid var(--line-2)}
.lane-head .count{font-size:12.5px;color:var(--ink-3)}
.acard{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:18px 20px;box-shadow:var(--sh-sm);margin-bottom:12px}
.acard-top{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}
.acard h3{font-size:1.04rem;font-weight:600;letter-spacing:-.01em;line-height:1.3}
.acard .tags{display:flex;gap:7px;flex-shrink:0;align-items:center}
.tag{font-size:11.5px;font-weight:500;padding:3px 9px;border-radius:999px;border:1px solid var(--line-2);color:var(--ink-2);white-space:nowrap}
.tag.fam{display:inline-flex;align-items:center;gap:6px}
.tag.fam .fdot{width:7px;height:7px;border-radius:50%}
.acard .rat{font-size:13.5px;color:var(--ink-2);margin:10px 0 0;max-width:72ch}
.acard .foot{display:flex;align-items:center;gap:14px;margin-top:13px;flex-wrap:wrap}
.impact{display:inline-flex;align-items:baseline;gap:6px;background:var(--inset);border:1px solid var(--line);border-radius:8px;padding:5px 10px}
.impact b{font-family:var(--serif);font-size:1.05rem;color:var(--positive)} .impact span{font-size:12px;color:var(--ink-3)}
.src{font-size:12px;color:var(--ink-3)} .src a{color:var(--accent-deep);text-decoration:none;border-bottom:1px solid var(--line-2)}
.ev{margin-top:11px;font-size:12.5px;color:var(--ink-2);border-left:2px solid var(--line-2);padding:2px 0 2px 11px;font-style:italic}
.ev .who{font-style:normal;font-family:var(--mono);font-size:11px;color:var(--ink-3);display:block;margin-bottom:2px}
details.apply{margin-top:12px;border-top:1px dashed var(--line-2);padding-top:10px}
details.apply summary{cursor:pointer;font-size:12.5px;font-weight:500;color:var(--accent-deep);list-style:none}
details.apply summary::before{content:"▸ ";color:var(--ink-3)}
details.apply[open] summary::before{content:"▾ "}
details.apply pre{font-family:var(--mono);font-size:12px;background:var(--inset);border:1px solid var(--line);
  border-radius:8px;padding:11px 13px;margin-top:9px;white-space:pre-wrap;color:var(--ink-2)}

/* stats */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.stat{background:var(--surface);padding:18px 16px;text-align:center}
.stat .n{font-family:var(--serif);font-size:1.9rem;color:var(--accent-deep);line-height:1}
.stat .c{font-size:12px;color:var(--ink-3);margin-top:5px}

.callout{display:flex;gap:13px;background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--accent);
  border-radius:var(--r);padding:15px 18px;margin:8px 0 26px;box-shadow:var(--sh-sm)}
.callout .ic{font-size:18px}
.callout p{font-size:13.5px;color:var(--ink-2)} .callout b{color:var(--ink)}
.callout code{font-family:var(--mono);font-size:12px;background:var(--surface-2);padding:1px 6px;border-radius:5px;color:var(--accent-deep)}

.divider{height:8px;background:var(--surface-2);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-top:40px}
footer{padding:30px 0 60px;color:var(--ink-3);font-size:12.5px;border-top:1px solid var(--line);margin-top:10px}
.pri.fyi{background:var(--surface-2);color:var(--ink-3)}
.sig .v{font-family:var(--sans);font-size:.95rem;font-weight:500;color:var(--ink);letter-spacing:0;margin:3px 0 0}
"""


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


_APPLY_LABEL = {"pending": "Apply", "selected": "✓ Selected for application",
                "applied": "Applied ✓", "skipped": "Skipped"}


def _apply_affordance(action_id, apply_kind, apply_preview, status):
    """Apply button (primary CTA) + a demoted 'View change' disclosure. advisory: no button."""
    if not apply_kind or apply_kind == "advisory":
        return ""
    st = status if status in _APPLY_LABEL else "pending"
    pressed = "true" if st == "selected" else "false"
    disabled = " disabled" if st in ("applied", "skipped") else ""
    btn = (f'<button class="apply-btn" type="button" data-action-id="{esc(action_id)}" '
           f'data-apply-kind="{esc(apply_kind)}" aria-pressed="{pressed}"{disabled}>'
           f'{esc(_APPLY_LABEL[st])}</button>')
    detail = (f'<details class="apply"><summary>View change</summary>'
              f'<pre>{esc(apply_preview)}</pre></details>') if apply_preview else ""
    return f'<div class="apply-row">{btn}</div>{detail}'


def action_card(title, family, effort, rationale_html, *, impact_html="",
                source_html="", evidence_html="", apply_kind="", apply_preview="",
                action_id="", status="pending"):
    st = status if status in _APPLY_LABEL else "pending"
    fam = (f'<span class="tag fam"><span class="fdot" style="background:var(--c-{esc(family)})">'
           f'</span>{esc(family)}</span>')
    eff = f'<span class="tag">{esc(effort)} effort</span>' if effort else ""
    foot_bits = []
    if impact_html:
        foot_bits.append(impact_html)
    if source_html:
        foot_bits.append(f'<span class="src">{source_html}</span>')
    foot = f'<div class="foot">{"".join(foot_bits)}</div>' if foot_bits else ""
    apply_html = _apply_affordance(action_id, apply_kind, apply_preview, st)
    return (f'<div class="acard" data-action-id="{esc(action_id)}" data-status="{esc(st)}">'
            f'<div class="acard-top"><h3>{esc(title)}</h3>'
            f'<div class="tags">{fam}{eff}</div></div>'
            f'<p class="rat">{rationale_html}</p>{foot}{evidence_html}{apply_html}</div>')


def footer(model_line, disclaimer):
    return (f'<footer><div class="wrap">'
            f'<b style="font-weight:600;color:var(--ink-2)">ClaudeCoach</b> &nbsp;·&nbsp; '
            f'{esc(model_line)}{esc(disclaimer)}</div></footer>')
