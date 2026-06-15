#!/usr/bin/env python3
"""coach_llm.py — the ONLY place that calls a model.

Headless invocation (verified against `claude --help` + a live smoke test):
    claude -p --model <model> --system-prompt <sys> --output-format text
with the user text piped to stdin. Captured stdout is the model's reply.

This is the A/B provider swap point: the subprocess detail lives here and
nowhere else. `runner` is an injectable callable(argv, stdin) -> str so tests
never shell out; the default runner shells to `claude`.

  call_text(system_prompt, user_text, model="claude-haiku-4-5", runner=None) -> str
  call_json(system_prompt, user_text, model="claude-haiku-4-5", runner=None) -> dict
"""
import json
import re
import subprocess

DEFAULT_MODEL = "claude-haiku-4-5"
MAX_RETRIES = 2  # extra attempts after the first; 3 total tries

# Greedy outermost-brace match — tolerates code fences / prose around the JSON.
_JSON_OBJECT = re.compile(r"\{.*\}", re.S)


def default_runner(argv, stdin):
    """Shell to `claude`, piping `stdin` and returning captured stdout."""
    res = subprocess.run(argv, input=stdin, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            "claude exited %d: %s" % (res.returncode, (res.stderr or "").strip()))
    return res.stdout


def _argv(system_prompt, model):
    return ["claude", "-p", "--model", model,
            "--system-prompt", system_prompt, "--output-format", "text"]


def call_text(system_prompt, user_text, model=DEFAULT_MODEL, runner=None):
    """Run the model and return its raw text reply (stripped).

    Retries on empty output up to MAX_RETRIES extra times, then raises.
    """
    runner = runner or default_runner
    argv = _argv(system_prompt, model)
    last_err = None
    for _ in range(MAX_RETRIES + 1):
        try:
            out = runner(argv, user_text)
        except Exception as ex:  # transient subprocess failure — retry
            last_err = ex
            continue
        if out and out.strip():
            return out.strip()
        last_err = ValueError("empty model output")
    raise RuntimeError("call_text failed after %d attempts: %s"
                       % (MAX_RETRIES + 1, last_err))


def extract_json(text):
    """First JSON object in `text`, tolerant of fences/prose. None if none parses."""
    if not text:
        return None
    m = _JSON_OBJECT.search(text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def call_json(system_prompt, user_text, model=DEFAULT_MODEL, runner=None):
    """Run the model and return the first JSON object from its reply.

    Retries on empty output OR unparseable JSON up to MAX_RETRIES extra times,
    then raises.
    """
    runner = runner or default_runner
    argv = _argv(system_prompt, model)
    last_err = None
    for _ in range(MAX_RETRIES + 1):
        try:
            out = runner(argv, user_text)
        except Exception as ex:
            last_err = ex
            continue
        if not (out and out.strip()):
            last_err = ValueError("empty model output")
            continue
        obj = extract_json(out)
        if obj is not None:
            return obj
        last_err = ValueError("no JSON object in model output")
    raise RuntimeError("call_json failed after %d attempts: %s"
                       % (MAX_RETRIES + 1, last_err))
