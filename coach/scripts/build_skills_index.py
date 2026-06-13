#!/usr/bin/env python3
"""build_skills_index.py — refresh coach/reference/skills_index.json from the
skill marketplace and Anthropic docs. Networked at BUILD TIME only; the index
ships in the repo so runtime stays local.

Degrades gracefully: if a source fails, it is SKIPPED and logged, and the
existing index entries for other sources are preserved — never ship a silently
half-built index.
"""
import argparse
import json
import sys

SOURCES = ["builtin", "marketplace", "anthropic-docs"]


def fetch_builtin():
    # Built-ins are known locally; return the curated seed entries unchanged.
    return None  # caller keeps existing 'builtin' entries


def fetch_marketplace():
    raise NotImplementedError("wire to the marketplace listing at implementation")


def fetch_anthropic_docs():
    raise NotImplementedError("wire to the docs index at implementation")


def build(existing, only=None):
    by_source = {}
    for e in existing.get("skills", []):
        by_source.setdefault(e.get("source", "builtin"), []).append(e)
    fetchers = {"marketplace": fetch_marketplace, "anthropic-docs": fetch_anthropic_docs}
    dropped = []
    for src, fn in fetchers.items():
        if only and src not in only:
            continue
        try:
            entries = fn()
            by_source[src] = entries
        except Exception as exc:  # skip + log, keep prior entries
            dropped.append("%s (%s)" % (src, exc.__class__.__name__))
    skills = [e for src in SOURCES for e in by_source.get(src, [])]
    if dropped:
        sys.stderr.write("WARNING: skipped sources: %s\n" % ", ".join(dropped))
    return {"built_at": existing.get("built_at"), "skills": skills,
            "dropped_sources": dropped}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="coach/reference/skills_index.json")
    ap.add_argument("--built-at", required=True, help="YYYY-MM-DD (pass today)")
    a = ap.parse_args()
    existing = json.load(open(a.index))
    out = build(existing)
    out["built_at"] = a.built_at
    json.dump(out, open(a.index, "w"), indent=2, ensure_ascii=False)
    print("wrote %s (%d skills, dropped=%s)"
          % (a.index, len(out["skills"]), out["dropped_sources"]))


if __name__ == "__main__":
    main()
