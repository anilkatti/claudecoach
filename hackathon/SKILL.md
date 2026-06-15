---
name: claude-code-coach
description: Coach anyone on how they use Claude Code. Point it at JSONL session logs and get a plain-English report — five friendly scores (Getting things done, Steering the AI, Quality bar, Thinking ahead, Working smart), how they're trending week over week, which habits help or hurt, and which skills to try or reconsider. Local, console-only, no upload. Use when the user wants to know how they're doing with Claude Code, whether they're improving, or what skills would help.
---

# Claude Code Coach

A plain-English coach for **everyone** using Claude Code — not just engineers.
Reuses the deterministic extraction pipeline in `scripts/` and adds a friendly
rubric, a weekly trend, habit coaching, and a skill recommender. Nothing leaves
the machine; the report stays in the terminal.

> **Status:** the extraction pipeline (`scripts/`) is ready. The coach-specific
> steps (7–10 below) are specified in
> `docs/superpowers/specs/2026-06-13-claude-code-coach-design.md` and being built
> per `docs/superpowers/plans/2026-06-13-claude-code-coach.md`. Until those land,
> run steps 1–6 and consult the plan for the rest.

## Pipeline (run in order)

Use a working directory like `/tmp/coach-run/` for intermediates. All scripts are
stdlib-only Python 3. Every LLM call is dispatched to **Claude Haiku 4.5**
(`model: haiku`); the orchestrating session never scores — it only runs the
deterministic scripts and relays prompts.

### 1. Resolve target sessions + repo
Default to the current project's logs:
- **Claude Code:** `~/.claude/projects/<encoded-cwd>/*.jsonl`, where
  `<encoded-cwd>` is the absolute working directory with every non-alphanumeric
  char replaced by `-`.
- **Codex CLI:** `~/.codex/sessions/**/*.jsonl` — keep only sessions whose `cwd`
  matches the target project. Skip if absent.

The git repo is the current working directory (episode linking needs it).

### 2. Condense (deterministic)
```
python3 scripts/condense.py <dir-or-files...> > condensed.jsonl
```
Skip sessions where `too_short` is true. Codex rollouts are auto-normalized.

### 3. Extract events + signals (deterministic)
```
python3 scripts/events.py <session.jsonl ...> > sessions.jsonl
```
Same session set that survived the `too_short` filter. Includes the
`skills_invoked` signal — which Claude Code skills/slash-commands were used.

### 4. Group commits + link episodes (deterministic)
```
python3 scripts/gitdata.py --repo <repo> --sessions sessions.jsonl --out gitdata.json
```

### 5. Narrate each session (Haiku)
For each scored session, dispatch a Haiku subagent with
`prompts/session_narrative.md` verbatim; input = the session's `condensed_text`.
Save to `narratives/<session_id>.md`.

### 6. Assemble episode inputs (deterministic)
```
python3 scripts/episodes.py --sessions sessions.jsonl --episodes gitdata.json --narratives narratives/ --out-dir inputs/
```

### 7. Score each episode (Haiku) — coach rubric
For each manifest entry, dispatch a Haiku subagent: governing instruction = full
text of `coach/prompts/coach_scoring.md` **verbatim**; input = the episode's
`inputs/<episode_id>.txt`. Output is the rubric JSON
(`title, what_happened, what_it_shows, caveat, confidence, scores{outcomes,
steering, quality, planning, leverage}`). Honor axis omission. Collect each
result wrapped with its manifest id (`{"episode_id": <id>, ...}`) into
`episodes.json`.

### 8. Aggregate
```
python3 coach/scripts/coach_aggregate.py episodes.json
```
Returns the five axes, overall score, and a softened band
(Getting started / Finding your footing / Solid / Strong / Exceptional).

### 9. Trend, habits, recommendations (deterministic + one Haiku rank)
```
python3 coach/scripts/trend.py  --episodes episodes.json --sessions sessions.jsonl --gitdata gitdata.json --out trend.json
python3 coach/scripts/habits.py --sessions sessions.jsonl --episodes episodes.json --catalog coach/reference/habit_catalog.json --out habits.json
python3 coach/scripts/recommend.py prep --aggregate agg.json --habits habits.json --sessions sessions.jsonl --index coach/reference/skills_index.json --out rec_input.json
```
Dispatch one Haiku subagent for the ranking: governing instruction =
`coach/prompts/skill_recommender.md` verbatim; input = `rec_input.json` →
`rec_raw.json`. Then:
```
python3 coach/scripts/recommend.py finalize --raw rec_raw.json --out recommendations.json
```

### 10. Render the report (deterministic)
```
python3 coach/scripts/coach_report.py \
  --episodes episodes.json --trend trend.json --habits habits.json \
  --recommendations recommendations.json --index coach/reference/skills_index.json \
  --repo-name <repo> --out report.md
```
Present `report.md` verbatim **in the console**. Do NOT produce an HTML artifact
or open anything in a browser.

## Honesty rails (do not skip)
- The scorer is **Claude Haiku 4.5**; scoring is **nondeterministic** — re-runs
  vary. Never present a number as definitive; it's a snapshot, not a verdict.
- Trend, habit, and "skills to reconsider" findings are **correlational**, stated
  as such, each backed by a counted evidence string. Never use causal language.
- The trend is **suppressed** below two ISO-week buckets — no fabricated line.
- `coach/reference/skills_index.json` shows its `built_at`; recommendations are
  only as current as the last index build.
- The report is **deterministic given its artifacts** (same inputs → byte-identical
  output) and **console-only**.
