#!/usr/bin/env python3
"""Per-project cache for capability_scout's verified output. The only reader/writer
of <profile_dir>/capabilities_cache.json. Deterministic plumbing — no judgment.
A cache is reused only when it was built for the SAME profile version and is within
TTL; otherwise the scout re-researches live and overwrites it."""

import argparse
import json
import os
from datetime import datetime, timezone

TTL_DAYS = 14  # cached research older than this is re-fetched; matches profile staleness
CACHE_NAME = "capabilities_cache.json"


def cache_path(profile_dir):
    return os.path.join(profile_dir, CACHE_NAME)


def load_cache(profile_dir):
    """Return the cache dict, or None if absent/unreadable."""
    p = cache_path(profile_dir)
    if not os.path.isfile(p):
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def is_fresh(cache, profile_generated_at, now_iso=None, ttl_days=TTL_DAYS):
    """True only when the cache was built for THIS profile version and within TTL.
    Tolerates naive or tz-aware timestamps (normalizes to UTC); any parse failure
    degrades to not-fresh, never a crash."""
    if not cache:
        return False
    if cache.get("profile_generated_at") != profile_generated_at:
        return False
    now = _aware(datetime.fromisoformat(now_iso)) if now_iso else datetime.now(timezone.utc)
    try:
        fetched = _aware(datetime.fromisoformat(
            str(cache.get("fetched_at", "")).replace("Z", "+00:00")))
    except (ValueError, TypeError):
        return False
    return (now - fetched).days < ttl_days


def write_cache(profile_dir, candidates, profile_generated_at, network_used, now_iso=None):
    """Persist the scout's candidates for this profile version; return the path written.
    No TTL is stored in the file; staleness is enforced at read time by is_fresh()."""
    now = now_iso or datetime.now(timezone.utc).isoformat()
    doc = {
        "schema_version": 1,
        "fetched_at": now,
        "profile_generated_at": profile_generated_at,
        "network_used": network_used,
        "candidates": candidates,
    }
    os.makedirs(profile_dir, exist_ok=True)
    p = cache_path(profile_dir)
    with open(p, "w") as f:
        json.dump(doc, f, indent=2)
    return p


def main():
    ap = argparse.ArgumentParser(description="Per-project capability cache.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status")
    s.add_argument("profile_dir")
    s.add_argument("--profile-generated-at", required=True)
    s.add_argument("--now", default=None)
    s.add_argument("--ttl-days", type=int, default=TTL_DAYS)

    w = sub.add_parser("write")
    w.add_argument("profile_dir")
    w.add_argument("candidates_json", help="path to a JSON file holding the candidates array")
    w.add_argument("--profile-generated-at", required=True)
    w.add_argument("--network-used", action="store_true")
    w.add_argument("--now", default=None)

    args = ap.parse_args()

    if args.cmd == "status":
        cache = load_cache(args.profile_dir)
        fresh = is_fresh(cache, args.profile_generated_at,
                         now_iso=args.now, ttl_days=args.ttl_days)
        print(json.dumps({
            "exists": cache is not None,
            "fresh": fresh,
            "fetched_at": (cache or {}).get("fetched_at"),
            "count": len((cache or {}).get("candidates", [])),
            "network_used": (cache or {}).get("network_used"),
        }))
    elif args.cmd == "write":
        with open(args.candidates_json) as f:
            candidates = json.load(f)
        p = write_cache(args.profile_dir, candidates, args.profile_generated_at,
                        args.network_used, now_iso=args.now)
        print(json.dumps({"written": p, "count": len(candidates)}))


if __name__ == "__main__":
    main()
