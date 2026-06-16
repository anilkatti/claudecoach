#!/usr/bin/env python3
"""Deterministic renderer: actions.json -> actions.html + a console summary.
The only joiner. Dark theme echoing profile-builder's visualize.py."""

import argparse
import html
import json
import os
import sys
import webbrowser

PRIORITIES = ["do_now", "consider", "fyi"]
PRIORITY_LABEL = {"do_now": "Do now", "consider": "Consider", "fyi": "FYI"}
SAFE_URL_SCHEMES = ("http://", "https://")


def _esc(x):
    """HTML-escape, coercing None to '' so a missing field never renders as 'None'."""
    return html.escape("" if x is None else str(x))


def group_by_priority(actions):
    g = {p: [] for p in PRIORITIES}
    for a in actions:
        g.get(a.get("priority", "fyi"), g["fyi"]).append(a)
    return g


def _evidence_lines(action):
    out = []
    for e in action.get("evidence", []):
        q = e.get("quote", "")
        out.append(f'      · {e.get("signal","")}: {q}')
    return out


def render_console(doc):
    g = group_by_priority(doc.get("actions", []))
    lines = [f'Recommendations for {doc.get("project_slug","")}',
             f'  profile {doc.get("profile_ref",{}).get("generated_at","?")} '
             f'(stale={doc.get("profile_ref",{}).get("stale")})  '
             f'network_used={doc.get("consent",{}).get("network_used")}', ""]
    for p in PRIORITIES:
        if not g[p]:
            continue
        lines.append(f'== {PRIORITY_LABEL[p]} ==')
        for a in g[p]:
            src = a.get("source", {})
            tag = f'  [{src.get("freshness","")}]' if src.get("freshness") else ""
            lines.append(f'  • {a.get("title","")}  ({a.get("family","")}/'
                         f'{a.get("effort","")} effort){tag}')
            lines.append(f'      {a.get("rationale","")}')
            lines += _evidence_lines(a)
        lines.append("")
    nr = doc.get("not_recommended", [])
    if nr:
        lines.append("== Considered but not recommended ==")
        for item in nr:
            lines.append(f'  • {item.get("considered","")} — {item.get("why_dropped","")}')
        lines.append("")
    lines.append(doc.get("disclaimer", ""))
    return "\n".join(lines)


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
    <div class="card {_esc(a.get('family',''))}">
      <div class="t">{_esc(a.get('title',''))}
        <span class="meta">{_esc(a.get('family',''))} · {_esc(a.get('effort',''))} effort{url}</span></div>
      <p>{_esc(a.get('rationale',''))} {impact} {fresh}</p>
      <ul class="ev">{ev}</ul>
      <details><summary>Apply ({_esc(apply_b.get('kind',''))})</summary><pre>{preview}</pre></details>
    </div>"""


def render_html(doc):
    g = group_by_priority(doc.get("actions", []))
    pr = doc.get("profile_ref", {})
    idx = doc.get("indexes", {})
    sections = []
    for p in PRIORITIES:
        if not g[p]:
            continue
        sections.append(f'<h2>{PRIORITY_LABEL[p]}</h2>' + "".join(_card(a) for a in g[p]))
    if not any(g[p] for p in PRIORITIES):
        sections.append("<p>No actions — your setup looks well tuned for this project.</p>")
    nr = doc.get("not_recommended", [])
    nr_html = ("".join(f'<li>{_esc(i.get("considered",""))} — '
                       f'{_esc(i.get("why_dropped",""))}</li>' for i in nr)
               if nr else "<li>none</li>")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>recommend-actions — {_esc(doc.get('project_slug',''))}</title>
<style>
body{{background:#0f1115;color:#e8eaed;font-family:-apple-system,system-ui,sans-serif;
max-width:900px;margin:0 auto;padding:32px;line-height:1.6}}
h1{{font-size:26px}} h2{{border-bottom:1px solid #2a3038;padding-bottom:6px;margin-top:32px}}
.card{{border:1px solid #2a3038;border-left-width:3px;border-radius:10px;padding:14px 16px;margin:12px 0;background:#161a21}}
.card.acquire{{border-left-color:#7aa2f7}} .card.config{{border-left-color:#e3b341}}
.card.author{{border-left-color:#bb9af7}} .card.behavior{{border-left-color:#7ee787}}
.t{{font-weight:600}} .meta{{color:#9aa4b2;font-weight:400;font-size:13px;margin-left:8px}}
.ev{{color:#9aa4b2;font-size:13px}} .src,.impact{{color:#7ee787;font-size:12px}}
a{{color:#7aa2f7}} pre{{background:#0f1115;padding:10px;border-radius:8px;overflow:auto}}
.fine{{color:#9aa4b2;font-size:12px;margin-top:32px;border-top:1px solid #2a3038;padding-top:12px}}
</style></head><body>
<h1>What would make Claude work better here</h1>
<p class="fine">profile {_esc(pr.get('generated_at','?'))} · stale={pr.get('stale')} ·
sessions sampled {_esc(pr.get('sessions_sampled','?'))} · network used {doc.get('consent',{}).get('network_used')} ·
capabilities {_esc(idx.get('capabilities_fetched_at','?'))}</p>
{''.join(sections)}
<h2>Considered but not recommended</h2><ul>{nr_html}</ul>
<p class="fine">{_esc(doc.get('disclaimer',''))}</p>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("actions_json")
    ap.add_argument("--html-out", default=None)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()
    with open(args.actions_json) as f:
        doc = json.load(f)
    print(render_console(doc))
    out = args.html_out or os.path.join(os.path.dirname(os.path.abspath(args.actions_json)),
                                        "actions.html")
    with open(out, "w") as f:
        f.write(render_html(doc))
    sys.stderr.write(f"\nWrote {out}\n")
    if not args.no_open:
        webbrowser.open(f"file://{os.path.abspath(out)}")


if __name__ == "__main__":
    main()
