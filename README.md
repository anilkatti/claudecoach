# Claude Code Coach

A local coach for **everyone** using Claude Code. Point it at your session logs
and get a plain-English report: how well you're working with the AI, whether
you're improving, which skills to try, and which habits are holding you back.
**Nothing leaves your machine — the report stays in your terminal.**

Not just for engineers. If you use Claude Code for writing, research, or ops,
the report speaks in outcomes and habits, not code jargon.

## What it does

```
your ~/.claude/projects/**/*.jsonl  (+ ~/.codex/sessions/**/*.jsonl)  + your repo
  → condense.py        (deterministic: drop tool/file bodies, scrub secrets, chunk)
  → events.py          (deterministic: events + signals, incl. which skills you used)
  → gitdata.py         (deterministic: group commits, link sessions into episodes)
  → narrative prompt   (Haiku)                      → per-session notes
  → episodes.py        (deterministic: assemble episode inputs)
  → coach_scoring      (Haiku, plain-English rubric) → 5 friendly scores
  → coach_aggregate.py (softened bands)              → overall + band
  → trend.py           (ISO-week buckets)            → how you're trending
  → habits.py          (rules over your signals)     → what's helping / hurting
  → recommend.py       (Haiku ranks a skills index)  → skills to try / reconsider
  → coach_report.py    (deterministic)               → your console report
```

## The five areas

| Area | What it means |
|---|---|
| **Getting things done** | Does your work with the AI actually reach finished results — or stall, loop, and get abandoned? |
| **Steering the AI** | How clearly you direct it and catch it going the wrong way. |
| **Quality bar** | Do you hold its output to a high standard — checking, verifying, not just accepting? |
| **Thinking ahead** | Do you set up the work before diving in, scaled to how big the task is? |
| **Working smart** | Do you use the right tools, skills, and habits to get more done with less effort? |

Scores run 1–10. Bands are encouraging, not harsh:
**Getting started · Finding your footing · Solid · Strong · Exceptional.**

## Honesty rails

- Scores come from **Claude Haiku 4.5** and are nondeterministic — a snapshot,
  not a verdict. Re-runs vary.
- Trend, habit, and "skills to reconsider" findings are **correlational** — they
  show up alongside each other, never proven to cause anything — and each is
  backed by a counted evidence string.
- The trend is **suppressed** until there are at least two weeks of sessions.
- Skill suggestions are only as current as the local skills index (its build
  date is shown in the report).
- The report is **deterministic given its inputs** and **console-only** — no HTML,
  nothing opened in a browser.

## Status

The deterministic **extraction pipeline** (`scripts/`) is ready and reused as-is.
The **coach layer** (rubric, trend, habits, recommender, report) is specified and
planned but being built — see:

- Design: [`docs/superpowers/specs/2026-06-13-claude-code-coach-design.md`](docs/superpowers/specs/2026-06-13-claude-code-coach-design.md)
- Implementation plan: [`docs/superpowers/plans/2026-06-13-claude-code-coach.md`](docs/superpowers/plans/2026-06-13-claude-code-coach.md)

## Requirements

Claude Code + Python 3 (standard library only — nothing to `pip install`).

> Analysis is **per-project**: it defaults to the logs for the repo you're in
> (`~/.claude/projects/<encoded-cwd>/`, plus Codex sessions whose `cwd` matches).
> Point it at another project's log dir to coach that one instead.

## Provenance

The deterministic extraction layer (condensing Claude Code / Codex JSONL,
event and signal extraction, commit grouping, session→episode linking, and
episode-input assembly) is an independent reimplementation that reads the
public Claude Code / Codex log formats. The rubric, narrative prompt, trend,
habit coaching, skill recommender, and report are all original to this project —
plain-English, written for a general audience. No third-party rubric text,
scoring prompt, or rule catalog is bundled.
