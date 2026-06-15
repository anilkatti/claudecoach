#!/usr/bin/env python3
"""review_message.py — review ONE typed user message into a coaching nudge.

Reads the message from stdin (or --message), runs it through `coach_llm` (the
single model call site) with `prompts/message_review.md`, and prints a small
review JSON to stdout:

    {"nudge": "...", "focus_axis": "steering", "scores": {"steering": 7.0}}

`nudge` is always present on success; `focus_axis` / `scores` are included only
when the model supplied valid values. With --out, the same JSON is also written
atomically to that path (e.g. ~/.claude/coach/nudge.json).

This is the live counterpart to the daily coach: same five axes, same model
call site, but scoped to a single message. The Rust island watcher shells out
to this script on each typed message and shows `nudge` in the expanded notch.
"""
import argparse
import json
import os
import sys
import tempfile

from coach_llm import DEFAULT_MODEL, call_json

# Same axis keys as coach/prompts/coach_scoring.md and coach/scripts/profile.py.
AXIS_KEYS = ("outcomes", "steering", "quality", "planning", "leverage")
PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "prompts", "message_review.md")


def load_prompt(path=PROMPT_PATH):
    with open(path, encoding="utf-8") as f:
        return f.read()


def normalize(obj):
    """Coerce a raw model dict into the review contract, or raise ValueError.

    Drops an unknown `focus_axis` and any non-numeric / unknown scores rather
    than failing — only a missing/empty `nudge` is fatal.
    """
    if not isinstance(obj, dict):
        raise ValueError("model output was not a JSON object")
    nudge = obj.get("nudge")
    nudge = nudge.strip() if isinstance(nudge, str) else ""
    if not nudge:
        raise ValueError("model output missing a non-empty 'nudge'")

    out = {"nudge": nudge}

    focus = obj.get("focus_axis")
    if isinstance(focus, str) and focus in AXIS_KEYS:
        out["focus_axis"] = focus

    scores = obj.get("scores")
    if isinstance(scores, dict):
        clean = {k: float(scores[k]) for k in AXIS_KEYS
                 if isinstance(scores.get(k), (int, float))
                 and not isinstance(scores.get(k), bool)}
        if clean:
            out["scores"] = clean
    return out


def review(message, model=DEFAULT_MODEL, runner=None, prompt=None):
    """Review `message` and return the normalized review dict (raises on failure).

    `runner` is forwarded to `coach_llm.call_json` so tests never shell out.
    """
    system_prompt = prompt if prompt is not None else load_prompt()
    obj = call_json(system_prompt, message, model=model, runner=runner)
    return normalize(obj)


def _atomic_write(path, data):
    """Write `data` to `path` via a temp file + rename (never a partial file)."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--message", help="message text (default: read stdin)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", help="also write the review JSON atomically here")
    a = ap.parse_args(argv)

    message = a.message if a.message is not None else sys.stdin.read()
    message = message.strip()
    if not message:
        print("review_message: no message provided", file=sys.stderr)
        return 2

    try:
        result = review(message, model=a.model)
    except Exception as ex:  # model/subprocess failure — Rust supplies a fallback
        print("review_message: %s" % ex, file=sys.stderr)
        return 1

    data = json.dumps(result, ensure_ascii=False)
    if a.out:
        _atomic_write(a.out, data)
    print(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
