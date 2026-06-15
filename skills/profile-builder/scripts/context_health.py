#!/usr/bin/env python3
"""Config-health probe for /profile-builder — the Goal-2 sensor.

Surfaces *raw signals* about the always-on context surface (what loads every
session) and the capability set: sizes, hooks, duplicate skills across install
levels, near-duplicate descriptions, MCP footprint, and owned-but-unused
capabilities. Plumbing only — it COLLECTS signals and renders NO verdicts; a
downstream coach skill decides what to trim. (Per the user's "collect, don't
judge" decision.)

Usage:
  python3 context_health.py <repo> [used_name ...]
Emits one JSON object to stdout.
"""
import glob
import json
import os
import re
import sys

# Run-as-script puts this dir on sys.path[0], so sibling plumbing imports work.
import inventory
from sessions import encode_cwd


# ----------------------------------------------------------- always-on context

def _count(path):
    """(lines, chars) for a file, or (0, 0) if absent/unreadable."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return 0, 0
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0), len(text)


def always_on_context(home, repo, slug):
    """Size the context that loads on (nearly) every session in this project:
    the global + repo CLAUDE.md and the project's auto-memory index. Only files
    that exist are reported. MEMORY.md lives under the project's logs dir
    (~/.claude/projects/<slug>/memory/), NOT in the repo — a path v1 got wrong."""
    candidates = [
        ("global", os.path.join(home, ".claude", "CLAUDE.md")),
        ("repo", os.path.join(repo, "CLAUDE.md")),
        ("repo", os.path.join(repo, ".claude", "CLAUDE.md")),
        ("memory", os.path.join(home, ".claude", "projects", slug, "memory", "MEMORY.md")),
    ]
    sources, total = [], 0
    for scope, path in candidates:
        if not os.path.isfile(path):
            continue
        lines, chars = _count(path)
        sources.append({"scope": scope, "path": path, "lines": lines, "chars": chars})
        total += chars
    return {"sources": sources, "total_chars": total, "est_tokens": total // 4}


# ------------------------------------------------------------------------ hooks

def _settings_files(home, repo):
    return [(os.path.join(home, ".claude", "settings.json"), "global"),
            (os.path.join(home, ".claude", "settings.local.json"), "global-local"),
            (os.path.join(repo, ".claude", "settings.json"), "repo"),
            (os.path.join(repo, ".claude", "settings.local.json"), "repo-local")]


def hooks(home, repo):
    """Per-event count of configured command hooks across all settings scopes.
    Hooks inject context every turn, so they're a prime always-on cost. Shape
    (verified on disk): settings["hooks"][event] = [{matcher?, hooks:[{command}]}]."""
    out = []
    for path, scope in _settings_files(home, repo):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        hk = data.get("hooks") if isinstance(data, dict) else None
        if not isinstance(hk, dict):
            continue
        for event, matchers in hk.items():
            count = 0
            for m in matchers if isinstance(matchers, list) else []:
                if isinstance(m, dict) and isinstance(m.get("hooks"), list):
                    count += len(m["hooks"])
            if count:
                out.append({"event": event, "scope": scope, "count": count})
    return sorted(out, key=lambda h: (h["scope"], h["event"]))


# --------------------------------------------------- capability set analysis ---

_CAP_KINDS = ("skills", "commands", "agents")


def find_duplicate_capabilities(inv):
    """Same capability name installed at more than one source (e.g. a skill in
    both ~/.claude and a plugin) — a redundancy/contradiction signal."""
    out = []
    for kind in _CAP_KINDS:
        by_name = {}
        for item in inv.get(kind, []):
            by_name.setdefault(item["name"], set()).add(item.get("source", "?"))
        for name, sources in sorted(by_name.items()):
            if len(sources) > 1:
                out.append({"name": name, "kind": kind, "sources": sorted(sources)})
    return out


def _tokens(text):
    return {w for w in re.findall(r"[a-z0-9]+", str(text or "").lower()) if len(w) >= 4}


def find_overlapping_capabilities(inv, threshold=0.6):
    """Skill pairs whose descriptions overlap heavily (Jaccard over content
    words) — candidate redundancy / triggering ambiguity. A signal, not a verdict."""
    skills = [s for s in inv.get("skills", []) if s.get("description")]
    toks = [(s["name"], _tokens(s["description"])) for s in skills]
    out = []
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            (na, a), (nb, b) = toks[i], toks[j]
            if na == nb or not a or not b:
                continue  # same name = a duplicate, reported separately
            overlap = len(a & b) / len(a | b)
            if overlap >= threshold:
                out.append({"a": na, "b": nb, "kind": "skills",
                            "overlap": round(overlap, 2)})
    return out


def mcp_footprint(inv):
    """How many MCP servers are configured, by source. Each server's tool
    definitions are loaded into context, so server count is a bloat proxy."""
    servers = inv.get("mcp_servers", [])
    by_source = {}
    for s in servers:
        by_source[s.get("source", "?")] = by_source.get(s.get("source", "?"), 0) + 1
    return {"servers": len(servers), "by_source": by_source}


def unused_capabilities(inv, used_names):
    """Owned skills/commands/agents whose name never appears in the sampled
    sessions — candidates to learn or remove. `used_names` is a set the caller
    derives from the per-session observations (skills_invoked)."""
    used = set(used_names or ())
    out = []
    for kind in _CAP_KINDS:
        for item in inv.get(kind, []):
            if item["name"] not in used:
                out.append({"name": item["name"], "kind": kind,
                            "source": item.get("source", "?")})
    return out


def health(repo=None, used_names=None, home=None):
    """Assemble the full config-health signal block for one repo."""
    repo = repo or os.getcwd()
    home = home or os.path.expanduser("~")
    slug = encode_cwd(repo)
    inv = inventory.inventory(repo)
    return {
        "always_on": always_on_context(home, repo, slug),
        "hooks": hooks(home, repo),
        "duplicate_capabilities": find_duplicate_capabilities(inv),
        "overlapping_capabilities": find_overlapping_capabilities(inv),
        "mcp_footprint": mcp_footprint(inv),
        "unused_capabilities": unused_capabilities(inv, used_names),
    }


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    repo = argv[0] if argv else os.getcwd()
    used = set(argv[1:]) if len(argv) > 1 else None
    json.dump(health(repo, used_names=used), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
