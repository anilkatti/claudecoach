#!/usr/bin/env python3
"""Phase-3 plumbing: write back an action's apply.status (applied|skipped|pending) in
actions.json. Deterministic only."""

import argparse
import json

VALID = ("applied", "skipped", "pending")


def set_status(doc, action_id, status):
    """Set apply.status for action_id; return True if the action was found."""
    for a in doc.get("actions", []):
        if a.get("id") == action_id:
            a.setdefault("apply", {})["status"] = status
            return True
    return False


def update_file(path, action_id, status):
    """Load actions.json, set one action's status, rewrite if found. Returns found-bool."""
    with open(path) as f:
        doc = json.load(f)
    found = set_status(doc, action_id, status)
    if found:
        with open(path, "w") as f:
            json.dump(doc, f, indent=2)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("action_id")
    ap.add_argument("status", choices=VALID)
    args = ap.parse_args()
    print(json.dumps({"updated": update_file(args.path, args.action_id, args.status)}))


if __name__ == "__main__":
    main()
