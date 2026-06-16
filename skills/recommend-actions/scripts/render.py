#!/usr/bin/env python3
"""Deterministic renderer: actions.json -> actions.html + a console summary.
The only joiner. Dark theme echoing profile-builder's visualize.py."""

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
    lines = [BANNER_TEXT, "",
             f'Recommendations for {doc.get("project_slug","")}',
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
    <div class="card action {_esc(a.get('family',''))}">
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
