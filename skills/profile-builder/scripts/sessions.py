#!/usr/bin/env python3
"""Plumbing for /profile-builder: discover, sample, condense, and scrub Claude
Code session transcripts for the current project. Deterministic only — no
interpretation (that is the LLM's job)."""

import argparse
import glob
import json
import os
import random
import re
import subprocess
import sys

# ---------------------------------------------------------------- discovery ---


def encode_cwd(path):
    """Encode an absolute path the way Claude Code names its project dirs:
    every non-alphanumeric character becomes '-' (no collapsing)."""
    return re.sub(r"[^a-zA-Z0-9]", "-", os.path.abspath(path))


def _projects_root():
    return os.path.expanduser("~/.claude/projects")


def list_worktrees(cwd):
    """Absolute paths of all git worktrees for the repo containing cwd (includes
    the main worktree). Empty list if cwd is not a git repo / git is absent."""
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return []
    return [ln[len("worktree "):].strip()
            for ln in out.splitlines() if ln.startswith("worktree ")]


def discover(cwd, projects_root=None):
    """Find session .jsonl files for the current project and its worktrees.
    Returns (slug, roots, files)."""
    projects_root = projects_root or _projects_root()
    roots = list_worktrees(cwd) or [os.path.abspath(cwd)]
    slug = encode_cwd(cwd)
    files, seen = [], set()
    for root in roots:
        s = encode_cwd(root)
        d = os.path.join(projects_root, s)
        if not os.path.isdir(d):
            continue
        for f in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
            if f not in seen:
                seen.add(f)
                files.append(f)
    return slug, roots, files


# ----------------------------------------------------------------- sampling ---

def sample(manifest, recent=20, tail=15, min_chars=800, seed=0):
    """Recency-stratified, seeded selection. manifest items need mtime,
    approx_chars, path. Returns (chosen, report)."""
    eligible = [m for m in manifest if m["approx_chars"] >= min_chars]
    # mtime desc, path asc -> fully deterministic ordering for seeded sampling
    by_recent = sorted(eligible, key=lambda m: (-m["mtime"], m["path"]))
    recent_set = by_recent[:recent]
    tail_pool = by_recent[recent:]
    if len(tail_pool) <= tail:
        tail_set = list(tail_pool)
    else:
        tail_set = random.Random(seed).sample(tail_pool, tail)
    chosen = recent_set + tail_set
    report = {
        "total": len(manifest),
        "eligible": len(eligible),
        "skipped_short": len(manifest) - len(eligible),
        "recent_taken": len(recent_set),
        "tail_sampled": len(tail_set),
        "tail_skipped": max(0, len(tail_pool) - len(tail_set)),
        "seed": seed,
    }
    return chosen, report


# ----------------------------------------------------------------- scrubbing --

_SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL), "private-key"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"), "anthropic-key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws-key"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "github-token"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "slack-token"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35,}"), "google-key"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}"), "jwt"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "openai-key"),
    (re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s:@/]+:[^\s:@/]+@\S+"), "db-url"),
    (re.compile(r"(?i)\b[A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD)\b\s*[=:]\s*[\"']?[A-Za-z0-9_\-./+]{8,}"), "env-secret"),
]


def scrub(text):
    """Redact common secret formats. Order matters (specific before generic)."""
    if not text:
        return text
    for pat, kind in _SECRET_PATTERNS:
        text = pat.sub("[REDACTED:%s]" % kind, text)
    return text


# ------------------------------------------------------------------ condense --

_MAX_TEXT = 20000
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Harness-injected wrappers that are not genuine user prompting. Skipped so the
# LLM reads real behavior, not slash-command / system machinery.
_MACHINERY_PREFIXES = (
    "<local-command-",
    "<command-name>", "<command-message>", "<command-args>",
    "<command-stdout>", "<command-contents>",
    "<system-reminder>",
    "Base directory for this skill:",  # Skill-tool load dumps the whole skill body
)


def _is_machinery(text):
    return text.lstrip().startswith(_MACHINERY_PREFIXES)


def _normalize_content(content):
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [(b if isinstance(b, dict) else {"type": "text", "text": b})
                for b in content if isinstance(b, (dict, str))]
    return []


def _short(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n] + "…"


def _render_tool_use(name, inp):
    inp = inp or {}
    if name in _WRITE_TOOLS:
        path = inp.get("file_path") or inp.get("notebook_path") or "?"
        body = inp.get("content") or inp.get("new_string") or inp.get("new_source") or ""
        return "TOOL_USE: %s(%s) [%d bytes]" % (name, path, len(str(body)))
    if name in ("Task", "Agent"):
        return "TOOL_USE: %s(%s) [%d bytes]" % (
            name, _short(inp.get("description", ""), 120), len(str(inp.get("prompt", ""))))
    if name == "Bash":
        return "TOOL_USE: Bash(%s)" % _short(scrub(inp.get("command", "")), 160)
    if name == "Skill":
        return "TOOL_USE: Skill(%s)" % (inp.get("skill") or inp.get("command") or "?")
    if name in ("Read", "Grep", "Glob"):
        arg = inp.get("file_path") or inp.get("pattern") or inp.get("path") or ""
        return "TOOL_USE: %s(%s)" % (name, _short(arg, 160))
    return "TOOL_USE: %s(%s)" % (name, _short(scrub(json.dumps(inp)), 160))


def condense(path):
    """Parse one session .jsonl into scrubbed condensed text + facts. Returns a
    dict, or None if the file can't be opened."""
    lines, n_user, first_prompt = [], 0, None
    facts = {"user_messages": 0, "assistant_messages": 0, "tool_uses": 0,
             "tool_results": 0, "code_edits": 0, "git_commits": 0,
             "subagent_dispatches": 0}
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return None
    with fh:
        for raw in fh:
            raw = raw.replace("\x00", "").strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg = entry.get("message") if isinstance(entry.get("message"), dict) else entry
            role = msg.get("role") or entry.get("type") or ""
            for b in _normalize_content(msg.get("content")):
                bt = b.get("type")
                if bt == "text":
                    txt = scrub(b.get("text", "")).strip()[:_MAX_TEXT]
                    if not txt or _is_machinery(txt):
                        continue
                    if role == "user":
                        n_user += 1
                        facts["user_messages"] += 1
                        if first_prompt is None:
                            first_prompt = _short(txt, 1000)
                        lines.append("USER: " + txt)
                    elif role == "assistant":
                        facts["assistant_messages"] += 1
                        lines.append("ASSISTANT: " + txt)
                    else:
                        lines.append("%s: %s" % (str(role).upper(), txt))
                elif bt == "tool_use":
                    name = b.get("name", "?")
                    facts["tool_uses"] += 1
                    if name in _WRITE_TOOLS:
                        facts["code_edits"] += 1
                    if name in ("Task", "Agent"):
                        facts["subagent_dispatches"] += 1
                    if name == "Bash" and "git commit" in str((b.get("input") or {}).get("command", "")):
                        facts["git_commits"] += 1
                    lines.append(_render_tool_use(name, b.get("input")))
                elif bt == "tool_result":
                    facts["tool_results"] += 1
                    content = b.get("content")
                    size = len(json.dumps(content)) if content is not None else 0
                    lines.append("[ToolResult: %d bytes]" % size)
    text = "\n".join(lines)
    return {
        "session_id": os.path.splitext(os.path.basename(path))[0],
        "path": path,
        "condensed_text": text,
        "approx_tokens": (len(text) + 3) // 4,
        "n_user_msgs": n_user,
        # Trivial = no genuine user prompt at all, or almost no content. A single
        # substantial prompt (e.g. a headless/programmatic run) is analyzable.
        "too_short": n_user < 1 or len(text) < 200,
        "first_prompt": first_prompt or "",
        "facts": facts,
    }


# ------------------------------------------------------------------ prepare ---

def _stat(path):
    try:
        return os.path.getmtime(path), os.path.getsize(path)
    except OSError:
        return 0.0, 0


def prepare(cwd, recent=20, sample=15, min_chars=800, seed=0, projects_root=None):
    """discover -> sample -> condense -> scrub. Returns {slug, report, sessions}."""
    slug, roots, files = discover(cwd, projects_root=projects_root)
    manifest = []
    for f in files:
        mtime, nchars = _stat(f)
        manifest.append({"path": f,
                         "session_id": os.path.splitext(os.path.basename(f))[0],
                         "mtime": mtime, "approx_chars": nchars})
    chosen, report = globals()["sample"](manifest, recent, sample, min_chars, seed)
    report["worktrees"] = roots
    sessions_out, failures = [], 0
    for m in chosen:
        c = condense(m["path"])
        if c is None:
            failures += 1
            continue
        sessions_out.append(c)
    report["condense_failures"] = failures
    report["too_short_chosen"] = sum(1 for s in sessions_out if s["too_short"])
    return {"slug": slug, "report": report, "sessions": sessions_out}


def main(argv=None):
    ap = argparse.ArgumentParser(description="profile-builder session plumbing")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="discover+sample+condense+scrub -> JSON on stdout")
    p.add_argument("--cwd", default=os.getcwd())
    p.add_argument("--recent", type=int, default=20)
    p.add_argument("--sample", type=int, default=15)
    p.add_argument("--min-chars", type=int, default=800)
    p.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    if args.cmd == "prepare":
        out = prepare(args.cwd, args.recent, args.sample, args.min_chars, args.seed)
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
