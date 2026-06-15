---
name: claude-code-coach
description: Coach anyone on how they use Claude Code. Point it at JSONL session logs and get a plain-English report — five friendly scores (Getting things done, Steering the AI, Quality bar, Thinking ahead, Working smart), how they're trending week over week, which habits help or hurt, and which skills to try or reconsider. Local, console-only, no upload.
---

# Claude Code Coach

A plain-English coach for everyone using Claude Code — not just engineers.
Reuses the deterministic extraction pipeline in `../scripts/` and adds a
friendly rubric, a weekly trend, habit coaching, and a skill recommender.

## Pipeline (run in order)
Use a working dir like `/tmp/coach-run/`. All scripts are stdlib-only Python 3.

1. **Resolve sessions + repo** — default to the current project's logs
   (`~/.claude/projects/<encoded-cwd>/*.jsonl`, plus Codex sessions whose `cwd`
   matches, if present). The git repo is the current working directory.
2. **Condense:** `python3 scripts/condense.py <dir> > condensed.jsonl`
   (skip `too_short`).
3. **Events:** `python3 scripts/events.py <sessions...> > sessions.jsonl`
   (now includes `skills_invoked`).
4. **Git/episodes:** `gitdata.py` then `episodes.py` (unchanged).
5. **Narrate** each session (Haiku, `prompts/session_narrative.md` verbatim).
6. **Score** each episode (Haiku): governing instruction = full text of
   `coach/prompts/coach_scoring.md` verbatim. Collect into `episodes.json`
   wrapped with `episode_id`.
7. **Aggregate:** `python3 coach/scripts/coach_aggregate.py episodes.json`.
8. **Trend:** `python3 coach/scripts/trend.py --episodes episodes.json
   --sessions sessions.jsonl --gitdata gitdata.json --out trend.json`.
9. **Habits:** `python3 coach/scripts/habits.py --sessions sessions.jsonl
   --episodes episodes.json --catalog coach/reference/habit_catalog.json
   --out habits.json`.
10. **Recommend:** `python3 coach/scripts/recommend.py prep ...` → Haiku ranks
    with `coach/prompts/skill_recommender.md` → `recommend.py finalize ...` →
    `recommendations.json`.
11. **Report:** `python3 coach/scripts/coach_report.py ...` → present verbatim
    in the console.

## Honesty rails
- Scorer is Claude Haiku 4.5; scoring is nondeterministic — never present a
  number as definitive.
- Trend, habit, and "skills to reconsider" findings are correlational, stated
  as such, each backed by a counted evidence string. Never causal.
- Trend is suppressed below two ISO-week buckets.
- `skills_index.json` shows its `built_at`; recommendations are only as current
  as the last index build.
- Console-only — no HTML, never open a browser.
