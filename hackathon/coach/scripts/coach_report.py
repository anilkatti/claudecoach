#!/usr/bin/env python3
"""coach_report.py — deterministic, console-only coach report. Joins
episodes/trend/habits/recommendations on plain keys. Same discipline as a
templated report: every claim is a fixed template over counted evidence.
"""
import argparse
import json

import _shared  # noqa: F401
from coach_aggregate import AXES, AXIS_NAMES, band_for_score, rollup

WHAT = {
    "outcomes": "Does your work with the AI actually reach finished results?",
    "steering": "How clearly you direct it and catch it going the wrong way.",
    "quality": "Do you hold its output to a high standard?",
    "planning": "Do you set up the work before diving in?",
    "leverage": "Do you use the right tools and skills to do more with less?",
}


def render(ctx):
    L = []
    add = L.append
    eps = ctx["episodes"]
    per_axis, overall = rollup(eps)

    add("# Your Claude Code Coach Report — %s" % (ctx.get("repo_name") or "your work"))
    add("")

    # Verdict
    add("## How you're doing")
    add("")
    if overall is not None:
        ranked = sorted(per_axis, key=lambda a: (-per_axis[a], AXES.index(a)))
        best, worst = ranked[0], ranked[-1]
        add("**%s — %.1f out of 10.**" % (band_for_score(overall), overall))
        add("")
        add("Your strongest area is **%s** (%.1f). The one to work on next is "
            "**%s** (%.1f)." % (AXIS_NAMES[best], per_axis[best],
                                AXIS_NAMES[worst], per_axis[worst]))
        add("")
        add("| Area | Score | Where you're at | What this means |")
        add("|---|---|---|---|")
        for axis in AXES:
            if axis not in per_axis:
                continue
            add("| %s | %.1f | %s | %s |" % (
                AXIS_NAMES[axis], per_axis[axis],
                band_for_score(per_axis[axis]), WHAT[axis]))
    else:
        add("Not enough scored work yet to give you a picture.")
    add("")

    # Trend
    add("## How you're trending")
    add("")
    tr = ctx.get("trend") or {}
    if tr.get("deltas"):
        for axis in AXES:
            if axis in tr["deltas"]:
                d = tr["deltas"][axis]
                arrow = "up" if d > 0 else ("down" if d < 0 else "flat")
                add("- **%s**: %s (%+.1f across %d weeks)" % (
                    AXIS_NAMES[axis], arrow, d, len(tr["weeks"])))
    else:
        add("_%s_" % (tr.get("note") or "no trend data"))
    add("")

    # Habits
    add("## What's working / what's holding you back")
    add("")
    hs = (ctx.get("habits") or {}).get("habits") or []
    good = [h for h in hs if h["polarity"] == "strength"]
    bad = [h for h in hs if h["polarity"] != "strength"]
    if good:
        add("**Working for you:**")
        for h in good:
            add("- %s — %s _(%s)_" % (h["label"], h["coaching"], h["evidence"]))
        add("")
    if bad:
        add("**Holding you back:**")
        for h in bad:
            add("- %s — %s _(%s)_" % (h["label"], h["coaching"], h["evidence"]))
        add("")
    if not hs:
        add("No clear habit patterns yet.")
        add("")

    # Skills
    add("## Skills to try / reconsider")
    add("")
    rec = ctx.get("recommendations") or {}
    if rec.get("recommend"):
        add("**Try these:**")
        for r in rec["recommend"]:
            add("- **%s** — %s (helps: %s)" % (
                r["name"], r["why"], r.get("helps_axis", "")))
        add("")
    if rec.get("reconsider"):
        add("**Worth a second look (shows up alongside weaker results):**")
        for r in rec["reconsider"]:
            add("- **%s** — %s" % (r["name"], r["why"]))
        add("")
    if not rec.get("recommend") and not rec.get("reconsider"):
        add("No skill suggestions this time.")
        add("")

    # Episode highlights
    add("## What you did")
    add("")
    for e in sorted(eps, key=lambda e: -float(e.get("confidence") or 0)):
        if e.get("title"):
            add("- **%s** — %s" % (e["title"], e.get("what_it_shows", "")))
    add("")

    # Fine print
    add("## Fine print")
    add("")
    add("- Scores come from Claude Haiku 4.5 and will vary slightly between "
        "runs — treat this as a snapshot, not a verdict.")
    add("- Trend, habit, and skill findings are patterns that show up alongside "
        "each other, not proven causes.")
    add("- Skill suggestions are only as current as the skills list "
        "(built %s)." % (ctx.get("index_built_at") or "unknown"))
    return "\n".join(L)


def _load_episodes(path):
    data = json.load(open(path))
    return data.get("episodes", data) if isinstance(data, dict) else data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--trend", required=True)
    ap.add_argument("--habits", required=True)
    ap.add_argument("--recommendations", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--repo-name", default="your work")
    ap.add_argument("--out")
    a = ap.parse_args()
    ctx = {
        "repo_name": a.repo_name,
        "episodes": _load_episodes(a.episodes),
        "trend": json.load(open(a.trend)),
        "habits": json.load(open(a.habits)),
        "recommendations": json.load(open(a.recommendations)),
        "index_built_at": json.load(open(a.index)).get("built_at"),
    }
    md = render(ctx)
    if a.out:
        open(a.out, "w").write(md)
    print(md)


if __name__ == "__main__":
    main()
