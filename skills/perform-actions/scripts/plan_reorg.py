#!/usr/bin/env python3
"""Phase-3 plumbing: from actions.json + the ids the user approved, select the
edit_file actions and group them by apply.target_path, so each context document gets a
single coherent reorganizer pass. Deterministic only."""

import argparse
import json


def group_edits(doc, approved_ids):
    """Return [{target_path, action_ids}] for approved edit_file actions, grouped by
    target_path. Non-edit_file, unapproved, and target_path-less actions are excluded.
    Group order = first appearance; ids within a group keep document order."""
    approved = set(approved_ids)
    groups = {}
    for a in doc.get("actions", []):
        if a.get("id") not in approved:
            continue
        ap = a.get("apply", {})
        if ap.get("kind") != "edit_file":
            continue
        tp = ap.get("target_path")
        if not tp:
            continue
        groups.setdefault(tp, []).append(a["id"])
    return [{"target_path": tp, "action_ids": ids} for tp, ids in groups.items()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("actions_json")
    ap.add_argument("approved_ids", nargs="*")
    args = ap.parse_args()
    with open(args.actions_json) as f:
        doc = json.load(f)
    print(json.dumps(group_edits(doc, args.approved_ids)))


if __name__ == "__main__":
    main()
