#!/usr/bin/env python3
"""coach_aggregate.py — roll per-episode coach scores up to an overall + band.

Five plain-English axes; bands keep fixed numeric cuts with friendly labels.
Rollup = confidence-weighted mean per axis, then mean of the per-axis means.
Scores are Haiku-judged and nondeterministic — this is a snapshot, not a verdict.
"""
import json
import sys

AXES = ["outcomes", "steering", "quality", "planning", "leverage"]

AXIS_NAMES = {
    "outcomes": "Getting things done",
    "steering": "Steering the AI",
    "quality": "Quality bar",
    "planning": "Thinking ahead",
    "leverage": "Working smart",
}

# (label, lo, hi) — fixed numeric cuts; labels softened/encouraging.
BANDS = [
    ("Getting started", 0, 4),
    ("Finding your footing", 4, 6),
    ("Solid", 6, 8),
    ("Strong", 8, 9),
    ("Exceptional", 9, 10.0001),
]


def band_for_score(score):
    for name, lo, hi in BANDS:
        if lo <= score < hi:
            return name
    return "Exceptional" if score >= 9 else "Getting started"


def rollup(episodes):
    per_axis = {}
    for axis in AXES:
        num = den = 0.0
        for ep in episodes:
            scores = (ep or {}).get("scores") or {}
            if axis in scores and isinstance(scores[axis], (int, float)):
                conf = ep.get("confidence", 0.8)
                w = float(conf) if isinstance(conf, (int, float)) else 0.8
                num += float(scores[axis]) * w
                den += w
        if den > 0:
            per_axis[axis] = round(num / den, 2)
    overall = round(sum(per_axis.values()) / len(per_axis), 2) if per_axis else None
    return per_axis, overall


def main():
    raw = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
    episodes = json.loads(raw)
    if isinstance(episodes, dict):
        episodes = episodes.get("episodes", [])
    per_axis, overall = rollup(episodes)
    out = {
        "episodes_scored": len(episodes),
        "axes": per_axis,
        "overall_score": overall,
        "band": band_for_score(overall) if overall is not None else None,
        "_disclaimer": "Haiku-scored and nondeterministic; a snapshot, not a verdict.",
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
