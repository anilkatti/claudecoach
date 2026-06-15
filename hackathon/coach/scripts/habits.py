#!/usr/bin/env python3
"""habits.py — deterministic habit detection over session signals.

A habit fires when its rule holds for a MAJORITY of sessions that carry the
signal. Findings are correlational; evidence is a counted "N of M" string.
"""
import argparse
import json

_OPS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
}


def _holds(rule, signals):
    sig = rule.get("signal")
    if sig not in signals or signals[sig] is None:
        return None  # signal absent -> session doesn't count
    op = _OPS.get(rule.get("op"))
    if op is None:
        return None
    return bool(op(signals[sig], rule.get("value")))


def detect(sessions, catalog):
    out = []
    for habit in catalog.get("habits", []):
        rule = habit.get("detect") or {}
        present = fired = 0
        for s in sessions:
            res = _holds(rule, s.get("session_signals") or {})
            if res is None:
                continue
            present += 1
            if res:
                fired += 1
        if present == 0 or fired * 2 <= present:  # need a strict majority
            continue
        out.append({
            "key": habit["key"],
            "label": habit["label"],
            "polarity": habit["polarity"],
            "coaching": habit["coaching"],
            "evidence": "%d of %d sessions" % (fired, present),
        })
    return {"habits": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", required=True)
    ap.add_argument("--episodes", required=False)  # reserved; not needed in v1
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sessions = [json.loads(l) for l in open(a.sessions) if l.strip()]
    catalog = json.load(open(a.catalog))
    out = detect(sessions, catalog)
    json.dump(out, open(a.out, "w"), indent=2, ensure_ascii=False)
    print("wrote %s (%d habits)" % (a.out, len(out["habits"])))


if __name__ == "__main__":
    main()
