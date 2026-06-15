#!/usr/bin/env python3
"""Enumerate the user's owned Claude Code capabilities across repo, personal, and
plugin levels. Plumbing only — no interpretation."""

import glob
import json
import os
import re
import sys


def _frontmatter(path):
    """Best-effort (name, description) from YAML frontmatter. stdlib only."""
    name = desc = ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return name, desc
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    block = m.group(1) if m else text[:2000]
    for line in block.splitlines():
        lm = re.match(r"\s*(name|description)\s*:\s*(.*?)\s*$", line)
        if lm:
            key, val = lm.group(1), lm.group(2).strip().strip("\"'")
            if key == "name" and not name:
                name = val
            elif key == "description" and not desc:
                desc = val
    if not name:
        name = (os.path.basename(os.path.dirname(path))
                if os.path.basename(path) == "SKILL.md"
                else os.path.splitext(os.path.basename(path))[0])
    return name, desc


def _collect(patterns):
    """patterns: list of (glob, source, recursive). Returns deduped entries."""
    out, seen = [], set()
    for pattern, source, recursive in patterns:
        for p in sorted(glob.glob(pattern, recursive=recursive)):
            name, desc = _frontmatter(p)
            key = (name, source)
            if key in seen:
                continue
            seen.add(key)
            out.append({"name": name, "description": desc, "source": source})
    return out


def _collect_mcp(repo):
    out, seen = [], set()
    files = [(os.path.join(repo, ".mcp.json"), "repo"),
             (os.path.expanduser("~/.mcp.json"), "personal"),
             (os.path.expanduser("~/.claude.json"), "personal"),
             (os.path.expanduser("~/.claude/settings.json"), "personal")]
    for path, source in files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        servers = data.get("mcpServers") if isinstance(data, dict) else None
        if isinstance(servers, dict):
            for name in servers:
                if name not in seen:
                    seen.add(name)
                    out.append({"name": name, "source": source})
    return out


def inventory(repo=None):
    repo = repo or os.getcwd()
    home = os.path.expanduser("~")
    return {
        "skills": _collect([
            (os.path.join(repo, ".claude/skills/*/SKILL.md"), "repo", False),
            (os.path.join(home, ".claude/skills/*/SKILL.md"), "personal", False),
            (os.path.join(home, ".claude/plugins/cache/**/skills/*/SKILL.md"), "plugin", True),
        ]),
        "commands": _collect([
            (os.path.join(repo, ".claude/commands/*.md"), "repo", False),
            (os.path.join(home, ".claude/commands/*.md"), "personal", False),
        ]),
        "agents": _collect([
            (os.path.join(repo, ".claude/agents/*.md"), "repo", False),
            (os.path.join(home, ".claude/agents/*.md"), "personal", False),
        ]),
        "mcp_servers": _collect_mcp(repo),
    }


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    repo = argv[0] if argv else os.getcwd()
    json.dump(inventory(repo), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
