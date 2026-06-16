#!/usr/bin/env python3
"""Phase-3 plumbing: resolve a cwd to its recommend-actions actions.json and validate
it parses. Deterministic only. Mirrors profile-builder's slug rule so it finds the same
per-project directory under ~/.claude/profiles/<slug>/."""

import argparse
import json
import os
import re


def encode_cwd(path):
    """Mirror the slug rule: every non-alphanumeric char -> '-'."""
    return re.sub(r"[^a-zA-Z0-9]", "-", os.path.abspath(path))


def _profiles_root(profiles_root=None):
    return profiles_root or os.path.expanduser("~/.claude/profiles")


def load_actions(cwd, profiles_root=None):
    """Return {doc, dir, slug, path} or {error: 'no_actions'|'bad_json', ...}."""
    slug = encode_cwd(cwd)
    d = os.path.join(_profiles_root(profiles_root), slug)
    p = os.path.join(d, "actions.json")
    if not os.path.isfile(p):
        return {"error": "no_actions", "dir": d, "slug": slug, "path": p}
    try:
        with open(p) as f:
            doc = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"error": "bad_json", "dir": d, "slug": slug, "path": p}
    return {"doc": doc, "dir": d, "slug": slug, "path": p}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cwd")
    ap.add_argument("--profiles-root", default=None)
    args = ap.parse_args()
    res = load_actions(args.cwd, profiles_root=args.profiles_root)
    if res.get("error"):
        print(json.dumps({"error": res["error"], "dir": res["dir"], "path": res["path"]}))
        return
    print(json.dumps({"slug": res["slug"], "dir": res["dir"], "path": res["path"],
                      "n_actions": len(res["doc"].get("actions", []))}))


if __name__ == "__main__":
    main()
