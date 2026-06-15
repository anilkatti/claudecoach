#!/usr/bin/env python3
"""Phase-2 plumbing: resolve a cwd to its profile-builder v2 profile, judge
freshness, and split the signals into four specialist lanes. Deterministic only."""

import argparse
import json
import os
import re
from datetime import datetime, timezone

MAX_AGE_DAYS = 14  # profiles older than this are flagged stale; overridable per-call


def encode_cwd(path):
    """Mirror profile-builder's slug rule: every non-alphanumeric char -> '-'."""
    return re.sub(r"[^a-zA-Z0-9]", "-", os.path.abspath(path))


def _profiles_root(profiles_root=None):
    return profiles_root or os.path.expanduser("~/.claude/profiles")


def load_profiles(cwd, profiles_root=None):
    """Return {project, user, dir, slug} or {error: 'no_profile', dir}."""
    slug = encode_cwd(cwd)
    d = os.path.join(_profiles_root(profiles_root), slug)
    proj_p = os.path.join(d, "project.profile.json")
    user_p = os.path.join(d, "user.profile.json")
    if not (os.path.isfile(proj_p) and os.path.isfile(user_p)):
        return {"error": "no_profile", "dir": d, "slug": slug}
    try:
        with open(proj_p) as f:
            project = json.load(f)
        with open(user_p) as f:
            user = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"error": "bad_json", "dir": d, "slug": slug}
    return {"project": project, "user": user, "dir": d, "slug": slug}


def freshness(project, now_iso=None, max_age_days=MAX_AGE_DAYS):
    """Compute age of the profile in whole days and whether it is stale.
    Tolerates naive OR tz-aware `generated_at`/`now_iso` (normalizes both to UTC)
    so an LLM-emitted timestamp without an offset degrades to stale, never a crash."""
    def _aware(dt):
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    now = _aware(datetime.fromisoformat(now_iso)) if now_iso else datetime.now(timezone.utc)
    gen = project.get("generated_at", "")
    try:
        when = _aware(datetime.fromisoformat(gen.replace("Z", "+00:00")))
        age_days = (now - when).days
    except (ValueError, TypeError):
        return {"generated_at": gen, "age_days": None, "stale": True}
    return {"generated_at": gen, "age_days": age_days, "stale": age_days > max_age_days}


def split_lanes(project, user):
    """Slice the two profiles into the four specialist lanes (see reference/schema.md)."""
    ch = user.get("context_health", {})
    return {
        "acquire": {
            "project_gaps": project.get("gaps", []),
            "user_gaps": user.get("gaps", []),
            "task_archetypes": project.get("task_archetypes", []),
            "domains": project.get("domains", []),
            "tools_and_materials": project.get("tools_and_materials", []),
            "owned_capabilities": user.get("owned_capabilities", {}),
            "mcp_footprint": ch.get("mcp_footprint", {}),
        },
        "config": {
            "context_health": ch,
            "friction_signals": user.get("friction_signals", []),
        },
        "author": {
            "friction_signals": user.get("friction_signals", []),
            "task_archetypes": project.get("task_archetypes", []),
            "owned_capabilities": user.get("owned_capabilities", {}),
        },
        "behavior": {
            "behavioral_signals": user.get("behavioral_signals", {}),
            "friction_signals": user.get("friction_signals", []),
            "habits": user.get("habits", []),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cwd")
    ap.add_argument("--profiles-root", default=None)
    ap.add_argument("--now", default=None, help="ISO8601 (test override)")
    args = ap.parse_args()

    loaded = load_profiles(args.cwd, profiles_root=args.profiles_root)
    if loaded.get("error"):
        print(json.dumps(loaded))
        return
    project, user = loaded["project"], loaded["user"]
    out = {
        "slug": loaded["slug"],
        "dir": loaded["dir"],
        "freshness": freshness(project, now_iso=args.now),
        "sessions_sampled": project.get("provenance", {}).get("sessions_sampled", 0),
        "lanes": split_lanes(project, user),
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
