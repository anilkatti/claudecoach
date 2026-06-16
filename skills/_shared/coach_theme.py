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
