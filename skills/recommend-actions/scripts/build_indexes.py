#!/usr/bin/env python3
"""Offline builder for the best-practices index. Pure normalize/merge/stamp
functions (unit-tested); the network fetch is a thin, intentionally un-unit-tested
CLI wrapper that degrades gracefully and logs every dropped source — never a silent
half-built index. NEVER hand-add an entry without a real source_url.

Capabilities are no longer a static index: capability_scout researches them live,
scoped to the profile, and the result is cached per project (see cache.py)."""

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone


def normalize_practice(raw):
    """Return a clean practice dict, or None if it has no verifiable source_url."""
    if not raw.get("id") or not raw.get("source_url"):
        return None
    return {"id": raw["id"], "principle": raw.get("principle", ""),
            "applies_to_signal": raw.get("applies_to_signal", ""),
            "source_url": raw["source_url"], "source_org": raw.get("source_org", "")}


def merge_by_key(existing, fetched, keys):
    """Union two record lists, deduping on `keys`; fetched records win."""
    out = {tuple(r.get(k) for k in keys): r for r in existing}
    out.update({tuple(r.get(k) for k in keys): r for r in fetched})
    return list(out.values())


def _build(sources, fetch_fn, normalize, dedupe_keys, now_iso, field):
    records, dropped = [], []
    for src in sources:
        try:
            for raw in fetch_fn(src):
                norm = normalize(raw)
                if norm:
                    records.append(norm)
                else:
                    dropped.append(f"{src}: record missing required fields")
        except Exception as exc:  # degrade gracefully; never silently truncate
            dropped.append(f"{src}: {exc}")
    merged = merge_by_key([], records, keys=dedupe_keys)
    return {"built_at": now_iso, field: merged, "dropped": dropped}


def build_practices(sources, fetch_fn, now_iso=None):
    now = now_iso or datetime.now(timezone.utc).isoformat()
    return _build(sources, fetch_fn, normalize_practice, ("id",), now, "practices")


def _fetch_json_url(url):
    """Thin build-time fetch: GET a URL returning a JSON array. Not unit-tested."""
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser(description="Build the best-practices index (offline).")
    ap.add_argument("--practices-url", action="append", default=[])
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    prac = build_practices(args.practices_url, _fetch_json_url)
    with open(f"{args.out_dir}/best_practices.json", "w") as f:
        json.dump(prac, f, indent=2)
    if prac["dropped"]:
        sys.stderr.write("DROPPED:\n  " + "\n  ".join(prac["dropped"]) + "\n")


if __name__ == "__main__":
    main()
