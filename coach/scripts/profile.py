#!/usr/bin/env python3
"""profile.py — pure/deterministic assembler of the coach profile.

Joins the aggregate (axes/overall/band), trend (delta/note), and counts into
one stable JSON snapshot. No model calls, no clock reads of its own — the
caller passes updated_at. Byte-deterministic for a given input.
"""
import argparse
import json

import _shared  # noqa: F401  (puts shared scripts on sys.path)
from coach_aggregate import AXES, AXIS_NAMES, band_for_score

AXIS_KEYS = ["outcomes", "steering", "quality", "planning", "leverage"]
DISCLAIMER = "Haiku-scored & nondeterministic; a snapshot, not a verdict."


def _extremes(axes):
    """(strongest, weakest) as {key,name,score}, or (None, None) if no axes.

    Ties broken by AXES order so the result is deterministic.
    """
    present = [(a, axes[a]) for a in AXES if a in axes]
    if not present:
        return None, None
    strongest = max(present, key=lambda kv: (kv[1], -AXES.index(kv[0])))
    weakest = min(present, key=lambda kv: (kv[1], AXES.index(kv[0])))

    def card(kv):
        a, v = kv
        return {"key": a, "name": AXIS_NAMES.get(a, a), "score": v}

    return card(strongest), card(weakest)


def build_profile(aggregate, trend, habits, recommendations,
                  n_sessions, updated_at):
    """Assemble the profile dict (EXACT schema; see module docstring).

    habits / recommendations are accepted for forward-compat but are not part
    of the emitted schema; pass None when unavailable.
    """
    axes_in = (aggregate or {}).get("axes") or {}
    axes = {k: axes_in[k] for k in AXIS_KEYS if k in axes_in}

    overall = (aggregate or {}).get("overall_score")
    band = (aggregate or {}).get("band")
    if band is None and overall is not None:
        band = band_for_score(overall)

    strongest, weakest = _extremes(axes)

    deltas = (trend or {}).get("deltas") or {}
    overall_delta = deltas.get("overall") if isinstance(deltas, dict) else None

    profile = {
        "updated_at": updated_at,
        "overall": overall,
        "band": band,
        "axes": axes,
        "trend": {
            "overall_delta": overall_delta,
            "note": (trend or {}).get("note"),
        },
        "n_sessions": n_sessions,
        "n_episodes": (aggregate or {}).get("episodes_scored"),
        "disclaimer": DISCLAIMER,
    }
    if strongest is not None:
        profile["strongest_axis"] = strongest
    if weakest is not None:
        profile["weakest_axis"] = weakest
    return profile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aggregate", required=True)
    ap.add_argument("--trend", required=True)
    ap.add_argument("--habits")
    ap.add_argument("--recommendations")
    ap.add_argument("--n-sessions", type=int, required=True)
    ap.add_argument("--updated-at", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    aggregate = json.load(open(a.aggregate))
    trend = json.load(open(a.trend))
    habits = json.load(open(a.habits)) if a.habits else None
    recommendations = json.load(open(a.recommendations)) if a.recommendations else None

    profile = build_profile(aggregate, trend, habits, recommendations,
                            a.n_sessions, a.updated_at)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False, sort_keys=True)
    print("wrote %s (overall=%s band=%s)"
          % (a.out, profile["overall"], profile["band"]))


if __name__ == "__main__":
    main()
