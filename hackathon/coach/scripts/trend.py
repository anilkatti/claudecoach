#!/usr/bin/env python3
"""trend.py — per-ISO-week trajectory of coach scores within one batch.

Dates each scored episode via its linked session timestamps, buckets by ISO
week, and reports a confidence-weighted per-axis mean per week plus first->last
deltas. Suppresses the trend below two buckets (no fabricated trajectory).
"""
import argparse
import datetime as _dt
import json

import _shared  # noqa: F401  (puts shared scripts on sys.path)
from coach_aggregate import AXES, rollup


def iso_week(ts):
    s = (ts or "").replace("Z", "+00:00")
    try:
        dt = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    y, w, _ = dt.isocalendar()
    return "%04d-W%02d" % (y, w)


def build(dated_episodes):
    """dated_episodes: [{week, scores, confidence}]. -> trend dict."""
    by_week = {}
    for ep in dated_episodes:
        wk = ep.get("week")
        if wk:
            by_week.setdefault(wk, []).append(ep)
    weeks = []
    for wk in sorted(by_week):
        per_axis, overall = rollup(by_week[wk])
        weeks.append({"week": wk, "axes": per_axis, "overall": overall,
                      "n_episodes": len(by_week[wk])})
    if len(weeks) < 2:
        return {"weeks": weeks, "deltas": None,
                "note": "not enough time span to show a trend yet"}
    first, last = weeks[0], weeks[-1]
    deltas = {}
    for axis in AXES:
        if axis in first["axes"] and axis in last["axes"]:
            deltas[axis] = round(last["axes"][axis] - first["axes"][axis], 2)
    if first["overall"] is not None and last["overall"] is not None:
        deltas["overall"] = round(last["overall"] - first["overall"], 2)
    return {"weeks": weeks, "deltas": deltas, "note": None}


def _episode_session_ids(ep):
    """Session ids linked to a gitdata episode. Real gitdata schema carries a
    flat `session_ids` list; fall back to `links[].session_id`."""
    ids = [sid for sid in (ep.get("session_ids") or []) if sid]
    if ids:
        return ids
    return [l.get("session_id") for l in (ep.get("links") or [])
            if l.get("session_id")]


def _date_episodes(episodes, sessions, gitdata):
    """Attach an ISO week to each scored episode via its linked sessions."""
    sess_ts = {s.get("session_id"): s.get("session_created_at")
               for s in sessions}
    ep_sessions = {ep.get("episode_id"): _episode_session_ids(ep)
                   for ep in (gitdata.get("episodes") or [])}
    dated = []
    for ep in episodes:
        eid = ep.get("episode_id")
        weeks = [iso_week(sess_ts.get(sid)) for sid in ep_sessions.get(eid, [])]
        weeks = [w for w in weeks if w]
        if not weeks:
            continue
        dated.append({"week": sorted(weeks)[0], "scores": ep.get("scores") or {},
                      "confidence": ep.get("confidence", 0.8)})
    return dated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--sessions", required=True)
    ap.add_argument("--gitdata", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    episodes = json.load(open(a.episodes))
    if isinstance(episodes, dict):
        episodes = episodes.get("episodes", [])
    sessions = [json.loads(l) for l in open(a.sessions) if l.strip()]
    gitdata = json.load(open(a.gitdata))
    out = build(_date_episodes(episodes, sessions, gitdata))
    json.dump(out, open(a.out, "w"), indent=2, ensure_ascii=False)
    print("wrote %s (%d weeks)" % (a.out, len(out["weeks"])))


if __name__ == "__main__":
    main()
