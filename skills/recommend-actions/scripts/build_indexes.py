#!/usr/bin/env python3
"""Offline builder for the curated indexes. Pure normalize/merge/stamp functions
(unit-tested); the network fetch is a thin, intentionally un-unit-tested CLI
wrapper that degrades gracefully and logs every dropped source — never a silent
half-built index. NEVER hand-add an entry without a real url/source_url."""

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone

CAP_FIELDS = ("name", "kind", "source", "one_liner", "when_to_use", "tags", "url")


def normalize_capability(raw):
    """Return a clean capability dict, or None if it lacks a name+url to point to."""
    if not raw.get("name") or not raw.get("url"):
        return None
    return {k: raw.get(k, [] if k == "tags" else "") for k in CAP_FIELDS}


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


def build_capabilities(sources, fetch_fn, now_iso=None):
    now = now_iso or datetime.now(timezone.utc).isoformat()
    return _build(sources, fetch_fn, normalize_capability, ("name", "kind"), now, "capabilities")


def build_practices(sources, fetch_fn, now_iso=None):
    now = now_iso or datetime.now(timezone.utc).isoformat()
    return _build(sources, fetch_fn, normalize_practice, ("id",), now, "practices")


def _fetch_json_url(url):
    """Thin build-time fetch: GET a URL returning a JSON array. Not unit-tested."""
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser(description="Build curated indexes (offline).")
    ap.add_argument("--capabilities-url", action="append", default=[])
    ap.add_argument("--practices-url", action="append", default=[])
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    cap = build_capabilities(args.capabilities_url, _fetch_json_url)
    prac = build_practices(args.practices_url, _fetch_json_url)
    with open(f"{args.out_dir}/capabilities_index.json", "w") as f:
        json.dump(cap, f, indent=2)
    with open(f"{args.out_dir}/best_practices.json", "w") as f:
        json.dump(prac, f, indent=2)
    if cap["dropped"] or prac["dropped"]:
        sys.stderr.write("DROPPED:\n  " + "\n  ".join(cap["dropped"] + prac["dropped"]) + "\n")


if __name__ == "__main__":
    main()
