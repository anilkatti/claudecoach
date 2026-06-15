#!/usr/bin/env python3
"""recommend.py — assemble the recommender's input (prep) and finalize its
output. The ranking itself is a Haiku call the skill makes with
coach/prompts/skill_recommender.md verbatim; this script does only the
deterministic work around it.

  recommend.py prep --aggregate agg.json --habits habits.json
                    --sessions sessions.jsonl --index coach/reference/skills_index.json
                    --out rec_input.json
  (skill dispatches Haiku: prompt = skill_recommender.md, input = rec_input.json
   -> rec_raw.json)
  recommend.py finalize --raw rec_raw.json --out recommendations.json
"""
import argparse
import json

import _shared  # noqa: F401
from coach_aggregate import AXIS_NAMES

MAX_RECOMMEND = 5


def prep(per_axis, habits, skills_used, index):
    used = {s.lstrip("/") for s in (skills_used or [])}
    weak = sorted(((a, v) for a, v in (per_axis or {}).items()),
                  key=lambda kv: kv[1])
    weak_axes = [{"axis": a, "name": AXIS_NAMES.get(a, a), "score": v}
                 for a, v in weak]
    catalog = [s for s in (index.get("skills") or [])
               if s.get("name") not in used]
    return {
        "weak_axes": weak_axes,
        "habits": [h for h in (habits.get("habits") or [])],
        "skills_used": sorted(used),
        "catalog": catalog,
    }


def finalize(raw):
    rec = (raw or {}).get("recommend") or []
    rec = rec[:MAX_RECOMMEND]
    return {"recommend": rec, "reconsider": (raw or {}).get("reconsider") or []}


def _skills_used_from_sessions(sessions):
    names = set()
    for s in sessions:
        inv = ((s.get("session_signals") or {}).get("skills_invoked") or {})
        for n in (inv.get("by_name") or {}):
            names.add(n)
    return sorted(names)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep")
    p.add_argument("--aggregate", required=True)
    p.add_argument("--habits", required=True)
    p.add_argument("--sessions", required=True)
    p.add_argument("--index", required=True)
    p.add_argument("--out", required=True)
    f = sub.add_parser("finalize")
    f.add_argument("--raw", required=True)
    f.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "prep":
        agg = json.load(open(a.aggregate))
        habits = json.load(open(a.habits))
        sessions = [json.loads(l) for l in open(a.sessions) if l.strip()]
        index = json.load(open(a.index))
        payload = prep(agg.get("axes") or {}, habits,
                       _skills_used_from_sessions(sessions), index)
        json.dump(payload, open(a.out, "w"), indent=2, ensure_ascii=False)
        print("wrote %s (%d catalog skills)" % (a.out, len(payload["catalog"])))
    else:
        out = finalize(json.load(open(a.raw)))
        json.dump(out, open(a.out, "w"), indent=2, ensure_ascii=False)
        print("wrote %s (%d recommended)" % (a.out, len(out["recommend"])))


if __name__ == "__main__":
    main()
