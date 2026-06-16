#!/usr/bin/env python3
"""Deterministic renderer: actions.json -> actions.html + a console summary.
The only joiner. Renders via the shared coach_theme (skills/_shared)."""

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
