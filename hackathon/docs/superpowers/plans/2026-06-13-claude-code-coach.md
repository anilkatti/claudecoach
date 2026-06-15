# Claude Code Coach Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new "Claude Code Coach" skill that scores anyone's Claude Code JSONL sessions on five plain-English axes, shows their week-over-week trend, coaches their habits, and recommends skills to adopt or reconsider — all locally, console-only.

**Architecture:** New product under `coach/`, reusing the existing tool-agnostic extraction scripts in `scripts/` (condense, events, gitdata, decisions, episodes) in place. The only change to a shared script is an *additive* skill-invocation detector in `events.py`. Everything coach-specific (rubric prompt, aggregate axes/bands, trend, habits, recommender, report) lives under `coach/` and reads/writes flat JSON artifacts in a working dir; the report is the only joiner.

**Tech Stack:** Python 3 standard library only (matches the repo). Tests are `unittest` files named `test_*.py` next to the code, run via `python3 <path>` or `pytest`. LLM calls (scoring, recommender) are dispatched to Claude Haiku 4.5 by the orchestrating skill, exactly as `the prior assessment tool` does — the Python scripts only do deterministic work and prompt assembly.

**Design spec:** `docs/superpowers/specs/2026-06-13-claude-code-coach-design.md`

---

## File structure (locked)

Reused unchanged (one home, in `scripts/`): `condense.py`, `gitdata.py`, `decisions.py`, `episodes.py`.
Modified additively: `scripts/events.py` (+ skill detection) and `scripts/test_events.py`.

New, under `coach/`:
```
coach/
  SKILL.md
  prompts/
    coach_scoring.md          # rubric the scorer reads (verbatim)
    skill_recommender.md      # recommender ranking prompt (verbatim)
  reference/
    habit_catalog.json        # habit detection rules + plain coaching copy
    skills_index.json         # curated skills corpus (built offline)
  scripts/
    _shared.py                # adds repo scripts/ to sys.path
    coach_aggregate.py        # 5 coach axes, softened bands, rollup
    trend.py                  # ISO-week trajectory
    habits.py                 # deterministic habit detection
    recommend.py              # assembles recommender input; finalizes output
    build_skills_index.py     # offline corpus builder (networked at build time)
    coach_report.py           # deterministic console report (the joiner)
    test_coach_aggregate.py
    test_trend.py
    test_habits.py
    test_recommend.py
    test_coach_report.py
```

Working-dir artifacts (contracts in spec §9): `episodes.json`, `trend.json`, `habits.json`, `recommendations.json`; repo-shipped `coach/reference/skills_index.json`.

---

## GROUP A — Foundation

### Task A1: Skill-invocation detection in events.py (shared, additive)

**Files:**
- Modify: `scripts/events.py` (add a `Skill` tool_use branch; add a slash-command method; add `skills_invoked` to event signals)
- Test: `scripts/test_events.py`

- [ ] **Step 1: Write the failing test**

Add to `scripts/test_events.py`:

```python
class SkillInvocationTests(unittest.TestCase):
    def test_skill_tool_use_becomes_event(self):
        ext = events.Extractor()
        ext.extract_from_tool_use(
            {"type": "tool_use", "name": "Skill",
             "input": {"skill": "brainstorming"}, "id": "t1"},
            "2026-06-01T10:00:00Z")
        evs = [e for e in ext.events if e["type"] == "skill_invoke"]
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["name"], "brainstorming")
        self.assertEqual(evs[0]["source"], "skill_tool")

    def test_slash_command_in_user_text_becomes_event(self):
        ext = events.Extractor()
        ext.extract_slash_command(
            "<command-name>/code-review</command-name>", "2026-06-01T10:01:00Z")
        evs = [e for e in ext.events if e["type"] == "skill_invoke"]
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["name"], "code-review")
        self.assertEqual(evs[0]["source"], "slash_command")

    def test_skills_invoked_signal_dedups_and_counts(self):
        evs = [
            {"type": "skill_invoke", "name": "brainstorming", "source": "skill_tool"},
            {"type": "skill_invoke", "name": "brainstorming", "source": "skill_tool"},
            {"type": "skill_invoke", "name": "code-review", "source": "slash_command"},
        ]
        sig = events._extract_event_signals(evs)
        self.assertEqual(sig["skills_invoked"]["total"], 3)
        self.assertEqual(sig["skills_invoked"]["unique"], 2)
        self.assertEqual(sig["skills_invoked"]["by_name"]["brainstorming"], 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/test_events.py SkillInvocationTests -v`
Expected: FAIL — `Extractor` has no `extract_slash_command`; `_extract_event_signals` returns no `skills_invoked`.

- [ ] **Step 3: Add the `Skill` branch in `extract_from_tool_use`**

In `scripts/events.py`, inside `extract_from_tool_use`, after the existing
`elif SUBAGENT_TOOL_NAME_PATTERN.fullmatch(tool_name):` block, add:

```python
        elif tool_name == "Skill":
            name = inp.get("skill") or inp.get("name")
            if not _blank(name):
                self.add_event("skill_invoke", timestamp,
                               name=str(name).lstrip("/"), source="skill_tool")
```

- [ ] **Step 4: Add the slash-command method**

Add near `extract_user_directive` in the `Extractor` class. The regex pulls the
command name out of a `<command-name>` tag (the tag form already recognized by
`LOCAL_COMMAND_TAGS`):

```python
    _SLASH_RE = re.compile(r"<command-name>\s*/?([\w:-]+)", re.I)

    def extract_slash_command(self, text, timestamp):
        if not text:
            return
        for m in self._SLASH_RE.finditer(text):
            self.add_event("skill_invoke", timestamp,
                           name=m.group(1), source="slash_command")
```

Wire it into the per-message loop: wherever raw user-message text is processed
(the same place `extract_raw_user_text` / `extract_user_directive` are called on
user text), add `self.extract_slash_command(<raw_user_text>, <timestamp>)`.
This is additive — slash-command tags are otherwise discarded.

- [ ] **Step 5: Add `skills_invoked` to `_extract_event_signals`**

In `_extract_event_signals(events)`, before its return, accumulate skill events:

```python
    skill_evs = [e for e in events if e.get("type") == "skill_invoke"]
    if skill_evs:
        by_name = {}
        for e in skill_evs:
            n = e.get("name") or "unknown"
            by_name[n] = by_name.get(n, 0) + 1
        signals["skills_invoked"] = {
            "total": len(skill_evs),
            "unique": len(by_name),
            "by_name": by_name,
        }
```

(Use whatever the local accumulator dict is named in that function in place of
`signals` if it differs.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 scripts/test_events.py -v`
Expected: PASS, including the new `SkillInvocationTests` and all existing tests
(the change is additive; nothing else should break).

- [ ] **Step 7: Commit**

```bash
git add scripts/events.py scripts/test_events.py
git commit -m "feat(events): detect Skill tool + slash-command invocations (additive)"
```

### Task A2: Coach skill scaffold + shared path helper

**Files:**
- Create: `coach/scripts/_shared.py`
- Create: `coach/SKILL.md`

- [ ] **Step 1: Create the shared-path helper**

`coach/scripts/_shared.py`:

```python
"""Add the repo's shared extraction scripts to sys.path so coach modules can
import condense/events/gitdata/decisions/episodes without copying them."""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SCRIPTS = os.path.join(_REPO, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

REPO_ROOT = _REPO
SHARED_SCRIPTS = _SCRIPTS
```

- [ ] **Step 2: Create the skill manifest**

`coach/SKILL.md`:

```markdown
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

1. **Resolve sessions + repo** — same as the prior assessment tool step 1
   (`~/.claude/projects/<encoded-cwd>/*.jsonl`, plus Codex if present).
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
```

- [ ] **Step 3: Verify the path helper imports a shared module**

Run: `python3 -c "import coach.scripts._shared as s; import sys; sys.path.insert(0, s.SHARED_SCRIPTS); import condense; print('ok')"`
Expected: prints `ok` (confirms shared imports resolve).

- [ ] **Step 4: Commit**

```bash
git add coach/scripts/_shared.py coach/SKILL.md
git commit -m "feat(coach): scaffold claude-code-coach skill + shared-path helper"
```

---

## GROUP B — Rubric

### Task B1: Coach aggregate (axes, softened bands, rollup)

**Files:**
- Create: `coach/scripts/coach_aggregate.py`
- Test: `coach/scripts/test_coach_aggregate.py`

- [ ] **Step 1: Write the failing test**

`coach/scripts/test_coach_aggregate.py`:

```python
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coach_aggregate as ca  # noqa: E402


class CoachAggregateTests(unittest.TestCase):
    def test_axes_are_the_five_plain_keys(self):
        self.assertEqual(ca.AXES,
                         ["outcomes", "steering", "quality", "planning", "leverage"])

    def test_band_labels_are_softened(self):
        self.assertEqual(ca.band_for_score(2.0), "Getting started")
        self.assertEqual(ca.band_for_score(5.0), "Finding your footing")
        self.assertEqual(ca.band_for_score(7.0), "Solid")
        self.assertEqual(ca.band_for_score(8.5), "Strong")
        self.assertEqual(ca.band_for_score(9.5), "Exceptional")

    def test_rollup_confidence_weighted_and_omits_unscored_axes(self):
        eps = [
            {"scores": {"outcomes": 8.0, "steering": 6.0}, "confidence": 1.0},
            {"scores": {"outcomes": 6.0}, "confidence": 0.5},
        ]
        per_axis, overall = ca.rollup(eps)
        self.assertAlmostEqual(per_axis["outcomes"], (8.0 + 6.0 * 0.5) / 1.5, places=2)
        self.assertEqual(per_axis["steering"], 6.0)
        self.assertNotIn("quality", per_axis)
        self.assertIsNotNone(overall)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 coach/scripts/test_coach_aggregate.py -v`
Expected: FAIL — `coach_aggregate` does not exist.

- [ ] **Step 3: Write the implementation**

`coach/scripts/coach_aggregate.py`:

```python
#!/usr/bin/env python3
"""coach_aggregate.py — roll per-episode coach scores up to an overall + band.

Five plain-English axes; bands keep the prior tool's numeric cuts with friendly labels.
Rollup = confidence-weighted mean per axis, then mean of the per-axis means.
Scores are Haiku-judged and nondeterministic — this is a snapshot, not a verdict.
"""
import json
import sys

AXES = ["outcomes", "steering", "quality", "planning", "leverage"]

AXIS_NAMES = {
    "outcomes": "Getting things done",
    "steering": "Steering the AI",
    "quality": "Quality bar",
    "planning": "Thinking ahead",
    "leverage": "Working smart",
}

# (label, lo, hi) — numeric cuts identical to the prior tool; labels softened.
BANDS = [
    ("Getting started", 0, 4),
    ("Finding your footing", 4, 6),
    ("Solid", 6, 8),
    ("Strong", 8, 9),
    ("Exceptional", 9, 10.0001),
]


def band_for_score(score):
    for name, lo, hi in BANDS:
        if lo <= score < hi:
            return name
    return "Exceptional" if score >= 9 else "Getting started"


def rollup(episodes):
    per_axis = {}
    for axis in AXES:
        num = den = 0.0
        for ep in episodes:
            scores = (ep or {}).get("scores") or {}
            if axis in scores and isinstance(scores[axis], (int, float)):
                conf = ep.get("confidence", 0.8)
                w = float(conf) if isinstance(conf, (int, float)) else 0.8
                num += float(scores[axis]) * w
                den += w
        if den > 0:
            per_axis[axis] = round(num / den, 2)
    overall = round(sum(per_axis.values()) / len(per_axis), 2) if per_axis else None
    return per_axis, overall


def main():
    raw = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
    episodes = json.loads(raw)
    if isinstance(episodes, dict):
        episodes = episodes.get("episodes", [])
    per_axis, overall = rollup(episodes)
    out = {
        "episodes_scored": len(episodes),
        "axes": per_axis,
        "overall_score": overall,
        "band": band_for_score(overall) if overall is not None else None,
        "_disclaimer": "Haiku-scored and nondeterministic; a snapshot, not a verdict.",
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 coach/scripts/test_coach_aggregate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add coach/scripts/coach_aggregate.py coach/scripts/test_coach_aggregate.py
git commit -m "feat(coach): aggregate with 5 plain axes + softened bands"
```

### Task B2: The scoring rubric prompt

**Files:**
- Create: `coach/prompts/coach_scoring.md`

- [ ] **Step 1: Write the rubric prompt**

`coach/prompts/coach_scoring.md` — plain "you" language, no engineering jargon,
keeps the effort-calibration and anti-halo discipline:

```markdown
You are coaching someone on how well they work *with* Claude Code (an AI
assistant). Score the PERSON's judgment across one work episode — not the AI's
output. The person may be writing, researching, doing ops, or coding; keep the
language plain and never assume they are an engineer.

Score the person's judgment about matching effort to the task. Quickly handing
off a small, well-described task is good judgment. Carefully setting up a big or
risky task before diving in is also good judgment. Penalize mismatches:
over-planning something trivial, or charging into something complex with no setup.

## What each axis means
### Getting things done (outcomes): Does the work actually finish?
1-2: Nothing lands. Work starts but loops, gets abandoned, or is undone.
3-4: A little gets finished, but lots of effort produces little result; the same
     thing gets redone without learning.
5-6: Things finish at a steady pace for the time spent.
7-8: Work reliably reaches a finished result, including on hard tasks. A short
     session that cleanly nails one tricky thing belongs here — it's result for
     effort, not volume.
9-10: Almost everything started gets finished and holds up, sustained across the
      whole stretch of work.

### Steering the AI (steering): Do they direct it well?
1-2: Takes whatever the AI produces.
3-4: Occasionally pushes back on bad output.
5-6: Gives reasonable direction and rejects clearly bad suggestions.
7-8: Direction fits the task — short and precise for small things, detailed for
     big ones. Catches wrong turns early and redirects.
9-10: Adapts how they work with the AI to each task. Their back-and-forth shows
      clear thinking and a high hit rate on the decisions that are hard to undo.

### Quality bar (quality): Do they hold the output to a high standard?
1-2: Accepts whatever comes out; no checking even when it matters.
3-4: Little checking or verification even where mistakes would bite.
5-6: Checks the things that matter; lighter touch on small stuff (which is fine).
7-8: Verifies where it counts, skips ceremony where it doesn't. Catches mistakes;
     cleans up as they go.
9-10: Consistently raises the standard — thorough checks where risk is high, light
      where it's low. The work gets cleaner over time.

### Thinking ahead (planning): Do they set up before diving in?
1-2: No forethought on complex work, OR wastes time over-planning trivial work.
3-4: Inconsistent; plans are thin when they exist.
5-6: Plans when the task warrants it, skips when it doesn't; plans are adequate.
7-8: Jumps straight into small tasks (correct), and brings real forethought to
     big ones — a sketch, a written plan, or clear reasoning before acting.
9-10: Plans match complexity precisely: detailed setup with checks and
      alternatives for hard work, quick decisive action on easy work.

### Working smart (leverage): Do they get more done with less effort?
1-2: Does everything the slow manual way; repeats work the tools could handle.
3-4: Rarely reaches for the right tool, skill, or shortcut.
5-6: Uses helpful tools and skills some of the time.
7-8: Picks the right tool/skill for the job and avoids wheel-spinning; their setup
     does real work for them.
9-10: Builds genuine leverage — the right skills, reusable setup, and habits that
      multiply what they get done.

## Calibration — use the whole 1-10 scale
- 7 is the typical capable person. Solid, unremarkable-for-the-task work is a 7.
  Most episodes land 5-8.
- Score each axis ONLY on its own evidence. The most common error is letting one
  impressive episode lift all five axes together (a "halo"). Resist it.
- Reserve 8 for clearly-above-typical, and 9-10 for the one or two axes that are
  genuinely exemplary. Grant 9-10 when the evidence supports it — don't withhold
  it out of caution.
- Use 3-5 when an axis is clearly below what the task needed. Both tails are real.
- Before finalizing, count axes at 8+. More than two is almost always a halo —
  move the merely-solid ones back to 6-7.

Output ONLY a JSON object:
{
  "title": "What they did, <=140 chars, plain and action-oriented",
  "what_happened": "2-3 sentences: what specifically happened this episode",
  "what_it_shows": "1-2 sentences: what this says about how they work",
  "caveat": "1 sentence: what might argue against a high score",
  "confidence": 0.8,
  "scores": {
    "outcomes": 7.0, "steering": 6.5, "quality": 7.0,
    "planning": 6.0, "leverage": 5.5
  }
}

Rules:
- Score the PERSON's judgment, not the AI's output.
- AXIS OMISSION: if an axis has no evidence this episode, omit the key entirely.
  Do not score it low as a default — omitting means "not enough to tell."
- For sessions with no finished artifact (exploration/learning): omit `outcomes`
  and `quality`; score the quality of their exploration on the other axes. Don't
  penalize for producing nothing when the intent was to understand.
- Use plain English everywhere. Never use internal jargon (execution leverage,
  spread drag, calibration signal). Don't state a lines-of-code number unless it
  appears verbatim in the input; describe scope in words instead.
```

- [ ] **Step 2: Verify it is valid and self-contained**

Run: `python3 -c "t=open('coach/prompts/coach_scoring.md').read(); assert 'Output ONLY a JSON object' in t and 'outcomes' in t and 'leverage' in t; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add coach/prompts/coach_scoring.md
git commit -m "feat(coach): plain-English 5-axis scoring rubric"
```

---

## GROUP C — Trend

### Task C1: ISO-week trend module

**Files:**
- Create: `coach/scripts/trend.py`
- Test: `coach/scripts/test_trend.py`

- [ ] **Step 1: Write the failing test**

`coach/scripts/test_trend.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trend  # noqa: E402


class TrendTests(unittest.TestCase):
    def test_iso_week_key(self):
        self.assertEqual(trend.iso_week("2026-06-01T10:00:00Z"), "2026-W23")

    def test_two_weeks_produce_deltas(self):
        dated = [
            {"week": "2026-W22", "scores": {"outcomes": 6.0}, "confidence": 1.0},
            {"week": "2026-W24", "scores": {"outcomes": 8.0}, "confidence": 1.0},
        ]
        out = trend.build(dated)
        self.assertEqual(len(out["weeks"]), 2)
        self.assertAlmostEqual(out["deltas"]["outcomes"], 2.0, places=2)
        self.assertIsNone(out.get("note"))

    def test_single_week_suppresses_trend(self):
        dated = [{"week": "2026-W22", "scores": {"outcomes": 6.0}, "confidence": 1.0}]
        out = trend.build(dated)
        self.assertEqual(len(out["weeks"]), 1)
        self.assertIsNone(out["deltas"])
        self.assertIn("not enough time span", out["note"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 coach/scripts/test_trend.py -v`
Expected: FAIL — `trend` module does not exist.

- [ ] **Step 3: Write the implementation**

`coach/scripts/trend.py`:

```python
#!/usr/bin/env python3
"""trend.py — per-ISO-week trajectory of coach scores within one batch.

Dates each scored episode via its linked session timestamps, buckets by ISO
week, and reports a confidence-weighted per-axis mean per week plus first->last
deltas. Suppresses the trend below two buckets (no fabricated trajectory).
"""
import argparse
import datetime as _dt
import json

import _shared  # noqa: F401  (puts shared scripts on sys.path)
from coach_aggregate import AXES, rollup


def iso_week(ts):
    s = (ts or "").replace("Z", "+00:00")
    try:
        dt = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    y, w, _ = dt.isocalendar()
    return "%04d-W%02d" % (y, w)


def build(dated_episodes):
    """dated_episodes: [{week, scores, confidence}]. -> trend dict."""
    by_week = {}
    for ep in dated_episodes:
        wk = ep.get("week")
        if wk:
            by_week.setdefault(wk, []).append(ep)
    weeks = []
    for wk in sorted(by_week):
        per_axis, overall = rollup(by_week[wk])
        weeks.append({"week": wk, "axes": per_axis, "overall": overall,
                      "n_episodes": len(by_week[wk])})
    if len(weeks) < 2:
        return {"weeks": weeks, "deltas": None,
                "note": "not enough time span to show a trend yet"}
    first, last = weeks[0], weeks[-1]
    deltas = {}
    for axis in AXES:
        if axis in first["axes"] and axis in last["axes"]:
            deltas[axis] = round(last["axes"][axis] - first["axes"][axis], 2)
    if first["overall"] is not None and last["overall"] is not None:
        deltas["overall"] = round(last["overall"] - first["overall"], 2)
    return {"weeks": weeks, "deltas": deltas, "note": None}


def _date_episodes(episodes, sessions, gitdata):
    """Attach an ISO week to each scored episode via its linked sessions."""
    sess_ts = {s.get("session_id"): s.get("session_created_at")
               for s in sessions}
    # episode_id -> [session_id,...] from gitdata episode linkage
    ep_sessions = {}
    for ep in (gitdata.get("episodes") or []):
        ep_sessions[ep.get("episode_id")] = [
            l.get("session_id") for l in (ep.get("linked_sessions") or [])
            if l.get("session_id")]
    dated = []
    for ep in episodes:
        eid = ep.get("episode_id")
        weeks = [iso_week(sess_ts.get(sid)) for sid in ep_sessions.get(eid, [])]
        weeks = [w for w in weeks if w]
        if not weeks:
            continue
        dated.append({"week": sorted(weeks)[0], "scores": ep.get("scores") or {},
                      "confidence": ep.get("confidence", 0.8)})
    return dated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--sessions", required=True)
    ap.add_argument("--gitdata", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    episodes = json.load(open(a.episodes))
    if isinstance(episodes, dict):
        episodes = episodes.get("episodes", [])
    sessions = [json.loads(l) for l in open(a.sessions) if l.strip()]
    gitdata = json.load(open(a.gitdata))
    out = build(_date_episodes(episodes, sessions, gitdata))
    json.dump(out, open(a.out, "w"), indent=2, ensure_ascii=False)
    print("wrote %s (%d weeks)" % (a.out, len(out["weeks"])))


if __name__ == "__main__":
    main()
```

> **Integration note:** `_date_episodes` reads `gitdata["episodes"][].linked_sessions[].session_id`. Confirm these key names against `gitdata.py`'s output during implementation; if they differ, adjust the two accessor lines only — the rest is schema-independent. Add a small fixture test if the shape is uncertain.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 coach/scripts/test_trend.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add coach/scripts/trend.py coach/scripts/test_trend.py
git commit -m "feat(coach): ISO-week trend with sub-two-bucket suppression"
```

---

## GROUP D — Habits

### Task D1: Habit catalog

**Files:**
- Create: `coach/reference/habit_catalog.json`

- [ ] **Step 1: Write the catalog**

`coach/reference/habit_catalog.json` — each rule references a signal field and a
comparison; `polarity` ∈ `strength|holding-you-back`:

```json
{
  "version": 1,
  "habits": [
    {
      "key": "vague-prompts",
      "label": "Your prompts are often very short",
      "polarity": "holding-you-back",
      "detect": {"signal": "median_words", "op": "<", "value": 4},
      "coaching": "Short prompts often show up alongside more back-and-forth. A sentence of context usually gets a better first answer."
    },
    {
      "key": "blind-acceptance",
      "label": "You rarely redirect the AI",
      "polarity": "holding-you-back",
      "detect": {"signal": "redirect_count", "op": "<", "value": 1},
      "coaching": "Sessions with no course-corrections often drift. Pushing back when something looks off tends to land better results."
    },
    {
      "key": "plans-before-big-work",
      "label": "You plan before big changes",
      "polarity": "strength",
      "detect": {"signal": "plan_mode_used", "op": "==", "value": true},
      "coaching": "Setting up before diving in tends to show up alongside finishing more of what you start."
    },
    {
      "key": "verifies-work",
      "label": "You check your work before calling it done",
      "polarity": "strength",
      "detect": {"signal": "tdd_discipline_ratio", "op": ">=", "value": 0.5},
      "coaching": "Verifying as you go tends to show up alongside fewer surprises later."
    },
    {
      "key": "works-in-parallel",
      "label": "You run work in parallel",
      "polarity": "strength",
      "detect": {"signal": "task_tool_used", "op": "==", "value": true},
      "coaching": "Delegating sub-tasks in parallel often shows up alongside getting more done per session."
    }
  ]
}
```

- [ ] **Step 2: Validate JSON**

Run: `python3 -c "import json; d=json.load(open('coach/reference/habit_catalog.json')); assert all('detect' in h and 'coaching' in h for h in d['habits']); print(len(d['habits']),'habits')"`
Expected: prints `5 habits`.

- [ ] **Step 3: Commit**

```bash
git add coach/reference/habit_catalog.json
git commit -m "feat(coach): habit catalog with plain coaching copy"
```

### Task D2: Habit detector

**Files:**
- Create: `coach/scripts/habits.py`
- Test: `coach/scripts/test_habits.py`

- [ ] **Step 1: Write the failing test**

`coach/scripts/test_habits.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import habits  # noqa: E402

CATALOG = {"habits": [
    {"key": "vague", "label": "short prompts", "polarity": "holding-you-back",
     "detect": {"signal": "median_words", "op": "<", "value": 4},
     "coaching": "add context"},
    {"key": "plans", "label": "plans ahead", "polarity": "strength",
     "detect": {"signal": "plan_mode_used", "op": "==", "value": True},
     "coaching": "keep it up"},
]}


class HabitTests(unittest.TestCase):
    def test_numeric_rule_fires_with_evidence(self):
        sessions = [{"session_signals": {"median_words": 2.0}},
                    {"session_signals": {"median_words": 3.0}}]
        out = habits.detect(sessions, CATALOG)
        keys = {h["key"]: h for h in out["habits"]}
        self.assertIn("vague", keys)
        self.assertIn("2 of 2", keys["vague"]["evidence"])

    def test_bool_rule_requires_majority(self):
        sessions = [{"session_signals": {"plan_mode_used": True}},
                    {"session_signals": {"plan_mode_used": False}},
                    {"session_signals": {"plan_mode_used": True}}]
        out = habits.detect(sessions, CATALOG)
        self.assertIn("plans", {h["key"] for h in out["habits"]})

    def test_no_fire_when_below_threshold(self):
        sessions = [{"session_signals": {"median_words": 10.0}}]
        out = habits.detect(sessions, CATALOG)
        self.assertNotIn("vague", {h["key"] for h in out["habits"]})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 coach/scripts/test_habits.py -v`
Expected: FAIL — `habits` module does not exist.

- [ ] **Step 3: Write the implementation**

`coach/scripts/habits.py`:

```python
#!/usr/bin/env python3
"""habits.py — deterministic habit detection over session signals.

A habit fires when its rule holds for a MAJORITY of sessions that carry the
signal. Findings are correlational; evidence is a counted "N of M" string.
"""
import argparse
import json

_OPS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
}


def _holds(rule, signals):
    sig = rule.get("signal")
    if sig not in signals or signals[sig] is None:
        return None  # signal absent -> session doesn't count
    op = _OPS.get(rule.get("op"))
    if op is None:
        return None
    return bool(op(signals[sig], rule.get("value")))


def detect(sessions, catalog):
    out = []
    for habit in catalog.get("habits", []):
        rule = habit.get("detect") or {}
        present = fired = 0
        for s in sessions:
            res = _holds(rule, s.get("session_signals") or {})
            if res is None:
                continue
            present += 1
            if res:
                fired += 1
        if present == 0 or fired * 2 <= present:  # need a strict majority
            continue
        out.append({
            "key": habit["key"],
            "label": habit["label"],
            "polarity": habit["polarity"],
            "coaching": habit["coaching"],
            "evidence": "%d of %d sessions" % (fired, present),
        })
    return {"habits": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", required=True)
    ap.add_argument("--episodes", required=False)  # reserved; not needed in v1
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sessions = [json.loads(l) for l in open(a.sessions) if l.strip()]
    catalog = json.load(open(a.catalog))
    out = detect(sessions, catalog)
    json.dump(out, open(a.out, "w"), indent=2, ensure_ascii=False)
    print("wrote %s (%d habits)" % (a.out, len(out["habits"])))


if __name__ == "__main__":
    main()
```

> **Note:** `redirect_count` referenced in the catalog must exist in
> `session_signals`. If `events.py` does not already emit it, either map the
> catalog rule to an existing signal (e.g. an imperative/directive count) or add
> the signal in a follow-up; a rule whose signal is absent simply never fires
> (safe). Keep catalog rules pointed at signals that exist.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 coach/scripts/test_habits.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add coach/scripts/habits.py coach/scripts/test_habits.py
git commit -m "feat(coach): deterministic habit detection with counted evidence"
```

---

## GROUP E — Skills recommender

### Task E1: Skills index builder + seed index

**Files:**
- Create: `coach/scripts/build_skills_index.py`
- Create: `coach/reference/skills_index.json` (seed, hand-written; builder refreshes it)

- [ ] **Step 1: Write a seed index**

`coach/reference/skills_index.json` (small hand-written seed so the recommender
works before the networked builder runs):

```json
{
  "built_at": "2026-06-13",
  "skills": [
    {"name": "brainstorming", "source": "builtin",
     "one_liner": "Turn an idea into a clear plan before building.",
     "when_to_use": "Starting any new feature or open-ended task.",
     "tags": ["planning", "steering"]},
    {"name": "code-review", "source": "builtin",
     "one_liner": "Review your changes for bugs and cleanups.",
     "when_to_use": "Before finishing or merging work.",
     "tags": ["quality"]},
    {"name": "verify", "source": "builtin",
     "one_liner": "Run the app and confirm a change actually works.",
     "when_to_use": "Before claiming something is done.",
     "tags": ["quality", "outcomes"]},
    {"name": "writing-plans", "source": "builtin",
     "one_liner": "Break a task into bite-sized, testable steps.",
     "when_to_use": "When a task has more than a couple of moving parts.",
     "tags": ["planning"]}
  ]
}
```

- [ ] **Step 2: Write the builder (graceful, build-time only)**

`coach/scripts/build_skills_index.py`:

```python
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
```

> **Note:** `--built-at` is passed in because the scripts must not call
> `Date.now()`-style nondeterminism inside logic; the orchestrating skill passes
> today's date. The two `fetch_*` functions are stubbed `NotImplementedError` so
> the seed index keeps working; wiring them to the real marketplace/docs is a
> bounded follow-up that does not block the recommender.

- [ ] **Step 3: Validate the seed index**

Run: `python3 -c "import json; d=json.load(open('coach/reference/skills_index.json')); assert d['built_at'] and d['skills']; print(len(d['skills']),'skills')"`
Expected: prints `4 skills`.

- [ ] **Step 4: Commit**

```bash
git add coach/scripts/build_skills_index.py coach/reference/skills_index.json
git commit -m "feat(coach): seed skills index + graceful offline builder"
```

### Task E2: Recommender prompt + prep/finalize

**Files:**
- Create: `coach/prompts/skill_recommender.md`
- Create: `coach/scripts/recommend.py`
- Test: `coach/scripts/test_recommend.py`

- [ ] **Step 1: Write the recommender prompt**

`coach/prompts/skill_recommender.md`:

```markdown
You help someone get more out of Claude Code by suggesting skills. You are given:
- their weakest scoring areas (with plain names),
- habits flagged as helping or holding them back,
- the skills they already use,
- a catalog of available skills (name, one-liner, when to use, tags).

Recommend skills that would most help their weak areas and bad habits, and that
they are NOT already using. Separately, flag any skill they already use that
tends to show up alongside their weak areas or bad habits ("reconsider") — phrase
these as correlations to look at, never as the cause.

Use plain language. Output ONLY this JSON:
{
  "recommend": [
    {"name": "<skill>", "why": "<one plain sentence>", "helps_axis": "<axis name>"}
  ],
  "reconsider": [
    {"name": "<skill they use>", "why": "<one plain, correlational sentence>"}
  ]
}
Recommend at most 5. Only include "reconsider" entries with real co-occurrence
evidence in the input; otherwise return an empty list.
```

- [ ] **Step 2: Write the failing test**

`coach/scripts/test_recommend.py`:

```python
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recommend  # noqa: E402


class RecommendTests(unittest.TestCase):
    def test_prep_excludes_already_used_and_lists_weak_axes(self):
        payload = recommend.prep(
            per_axis={"outcomes": 5.0, "steering": 7.5, "quality": 6.0,
                      "planning": 4.5, "leverage": 8.0},
            habits={"habits": [{"key": "vague", "label": "short prompts",
                                "polarity": "holding-you-back",
                                "coaching": "add context"}]},
            skills_used=["brainstorming"],
            index={"skills": [
                {"name": "brainstorming", "one_liner": "x", "tags": ["planning"]},
                {"name": "writing-plans", "one_liner": "y", "tags": ["planning"]}]},
        )
        names = [s["name"] for s in payload["catalog"]]
        self.assertIn("writing-plans", names)
        self.assertNotIn("brainstorming", names)  # already used -> excluded
        self.assertEqual(payload["weak_axes"][0]["axis"], "planning")  # lowest first

    def test_finalize_caps_and_passes_through(self):
        raw = {"recommend": [{"name": "a", "why": "w", "helps_axis": "x"}] * 7,
               "reconsider": []}
        out = recommend.finalize(raw)
        self.assertEqual(len(out["recommend"]), 5)
        self.assertEqual(out["reconsider"], [])
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 coach/scripts/test_recommend.py -v`
Expected: FAIL — `recommend` module does not exist.

- [ ] **Step 4: Write the implementation**

`coach/scripts/recommend.py`:

```python
#!/usr/bin/env python3
"""recommend.py — assemble the recommender's input (prep) and finalize its
output. The ranking itself is a Haiku call the skill makes with
coach/prompts/skill_recommender.md verbatim; this script does only the
deterministic work around it.

  recommend.py prep --aggregate agg.json --habits habits.json
                    --sessions sessions.jsonl --index coach/reference/skills_index.json
                    --out rec_input.json
  (skill dispatches Haiku: prompt = skill_recommender.md, input = rec_input.json
   -> rec_raw.json)
  recommend.py finalize --raw rec_raw.json --out recommendations.json
"""
import argparse
import json

import _shared  # noqa: F401
from coach_aggregate import AXIS_NAMES

MAX_RECOMMEND = 5


def prep(per_axis, habits, skills_used, index):
    used = {s.lstrip("/") for s in (skills_used or [])}
    weak = sorted(((a, v) for a, v in (per_axis or {}).items()),
                  key=lambda kv: kv[1])
    weak_axes = [{"axis": a, "name": AXIS_NAMES.get(a, a), "score": v}
                 for a, v in weak]
    catalog = [s for s in (index.get("skills") or [])
               if s.get("name") not in used]
    return {
        "weak_axes": weak_axes,
        "habits": [h for h in (habits.get("habits") or [])],
        "skills_used": sorted(used),
        "catalog": catalog,
    }


def finalize(raw):
    rec = (raw or {}).get("recommend") or []
    rec = rec[:MAX_RECOMMEND]
    return {"recommend": rec, "reconsider": (raw or {}).get("reconsider") or []}


def _skills_used_from_sessions(sessions):
    names = set()
    for s in sessions:
        inv = ((s.get("session_signals") or {}).get("skills_invoked") or {})
        for n in (inv.get("by_name") or {}):
            names.add(n)
    return sorted(names)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep")
    p.add_argument("--aggregate", required=True)
    p.add_argument("--habits", required=True)
    p.add_argument("--sessions", required=True)
    p.add_argument("--index", required=True)
    p.add_argument("--out", required=True)
    f = sub.add_parser("finalize")
    f.add_argument("--raw", required=True)
    f.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "prep":
        agg = json.load(open(a.aggregate))
        habits = json.load(open(a.habits))
        sessions = [json.loads(l) for l in open(a.sessions) if l.strip()]
        index = json.load(open(a.index))
        payload = prep(agg.get("axes") or {}, habits,
                       _skills_used_from_sessions(sessions), index)
        json.dump(payload, open(a.out, "w"), indent=2, ensure_ascii=False)
        print("wrote %s (%d catalog skills)" % (a.out, len(payload["catalog"])))
    else:
        out = finalize(json.load(open(a.raw)))
        json.dump(out, open(a.out, "w"), indent=2, ensure_ascii=False)
        print("wrote %s (%d recommended)" % (a.out, len(out["recommend"])))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 coach/scripts/test_recommend.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add coach/prompts/skill_recommender.md coach/scripts/recommend.py coach/scripts/test_recommend.py
git commit -m "feat(coach): skill recommender prep/finalize + ranking prompt"
```

---

## GROUP F — Report

### Task F1: Deterministic console report (the joiner)

**Files:**
- Create: `coach/scripts/coach_report.py`
- Test: `coach/scripts/test_coach_report.py`

- [ ] **Step 1: Write the failing test**

`coach/scripts/test_coach_report.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coach_report as cr  # noqa: F401


class CoachReportTests(unittest.TestCase):
    def _ctx(self):
        return {
            "repo_name": "demo",
            "episodes": [
                {"episode_id": 1, "title": "Shipped a fix",
                 "what_it_shows": "Closes loops cleanly.", "confidence": 0.9,
                 "scores": {"outcomes": 8.0, "steering": 6.0, "quality": 7.0,
                            "planning": 6.0, "leverage": 5.0}}],
            "trend": {"weeks": [{"week": "2026-W22", "axes": {"outcomes": 6.0},
                                 "overall": 6.0, "n_episodes": 1}],
                      "deltas": None, "note": "not enough time span to show a trend yet"},
            "habits": {"habits": [{"key": "vague", "label": "short prompts",
                                   "polarity": "holding-you-back",
                                   "coaching": "add context",
                                   "evidence": "2 of 3 sessions"}]},
            "recommendations": {"recommend": [
                {"name": "writing-plans", "why": "breaks work into steps",
                 "helps_axis": "Thinking ahead"}], "reconsider": []},
            "index_built_at": "2026-06-13",
        }

    def test_render_has_all_sections_and_plain_band(self):
        md = cr.render(self._ctx())
        self.assertIn("Getting things done", md)          # plain axis name
        self.assertIn("Solid", md)                         # softened band (overall 6.4)
        self.assertIn("not enough time span", md)          # trend suppression
        self.assertIn("short prompts", md)                 # habit
        self.assertIn("writing-plans", md)                 # recommendation
        self.assertIn("Haiku", md)                         # honesty fine print
        self.assertNotIn("Execution Leverage", md)         # no the prior tool jargon
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 coach/scripts/test_coach_report.py -v`
Expected: FAIL — `coach_report` does not exist / `render` undefined.

- [ ] **Step 3: Write the implementation**

`coach/scripts/coach_report.py`:

```python
#!/usr/bin/env python3
"""coach_report.py — deterministic, console-only coach report. Joins
episodes/trend/habits/recommendations on plain keys. Same discipline as
the prior assessment tool's report.py: every claim is a fixed template over counted evidence.
"""
import argparse
import json

import _shared  # noqa: F401
from coach_aggregate import AXES, AXIS_NAMES, band_for_score, rollup

WHAT = {
    "outcomes": "Does your work with the AI actually reach finished results?",
    "steering": "How clearly you direct it and catch it going the wrong way.",
    "quality": "Do you hold its output to a high standard?",
    "planning": "Do you set up the work before diving in?",
    "leverage": "Do you use the right tools and skills to do more with less?",
}


def render(ctx):
    L = []
    add = L.append
    eps = ctx["episodes"]
    per_axis, overall = rollup(eps)

    add("# Your Claude Code Coach Report — %s" % (ctx.get("repo_name") or "your work"))
    add("")

    # Verdict
    add("## How you're doing")
    add("")
    if overall is not None:
        ranked = sorted(per_axis, key=lambda a: (-per_axis[a], AXES.index(a)))
        best, worst = ranked[0], ranked[-1]
        add("**%s — %.1f out of 10.**" % (band_for_score(overall), overall))
        add("")
        add("Your strongest area is **%s** (%.1f). The one to work on next is "
            "**%s** (%.1f)." % (AXIS_NAMES[best], per_axis[best],
                                AXIS_NAMES[worst], per_axis[worst]))
        add("")
        add("| Area | Score | Where you're at | What this means |")
        add("|---|---|---|---|")
        for axis in AXES:
            if axis not in per_axis:
                continue
            add("| %s | %.1f | %s | %s |" % (
                AXIS_NAMES[axis], per_axis[axis],
                band_for_score(per_axis[axis]), WHAT[axis]))
    else:
        add("Not enough scored work yet to give you a picture.")
    add("")

    # Trend
    add("## How you're trending")
    add("")
    tr = ctx.get("trend") or {}
    if tr.get("deltas"):
        for axis in AXES:
            if axis in tr["deltas"]:
                d = tr["deltas"][axis]
                arrow = "up" if d > 0 else ("down" if d < 0 else "flat")
                add("- **%s**: %s (%+.1f across %d weeks)" % (
                    AXIS_NAMES[axis], arrow, d, len(tr["weeks"])))
    else:
        add("_%s_" % (tr.get("note") or "no trend data"))
    add("")

    # Habits
    add("## What's working / what's holding you back")
    add("")
    hs = (ctx.get("habits") or {}).get("habits") or []
    good = [h for h in hs if h["polarity"] == "strength"]
    bad = [h for h in hs if h["polarity"] != "strength"]
    if good:
        add("**Working for you:**")
        for h in good:
            add("- %s — %s _(%s)_" % (h["label"], h["coaching"], h["evidence"]))
        add("")
    if bad:
        add("**Holding you back:**")
        for h in bad:
            add("- %s — %s _(%s)_" % (h["label"], h["coaching"], h["evidence"]))
        add("")
    if not hs:
        add("No clear habit patterns yet.")
        add("")

    # Skills
    add("## Skills to try / reconsider")
    add("")
    rec = ctx.get("recommendations") or {}
    if rec.get("recommend"):
        add("**Try these:**")
        for r in rec["recommend"]:
            add("- **%s** — %s (helps: %s)" % (
                r["name"], r["why"], r.get("helps_axis", "")))
        add("")
    if rec.get("reconsider"):
        add("**Worth a second look (shows up alongside weaker results):**")
        for r in rec["reconsider"]:
            add("- **%s** — %s" % (r["name"], r["why"]))
        add("")
    if not rec.get("recommend") and not rec.get("reconsider"):
        add("No skill suggestions this time.")
        add("")

    # Episode highlights
    add("## What you did")
    add("")
    for e in sorted(eps, key=lambda e: -float(e.get("confidence") or 0)):
        if e.get("title"):
            add("- **%s** — %s" % (e["title"], e.get("what_it_shows", "")))
    add("")

    # Fine print
    add("## Fine print")
    add("")
    add("- Scores come from Claude Haiku 4.5 and will vary slightly between "
        "runs — treat this as a snapshot, not a verdict.")
    add("- Trend, habit, and skill findings are patterns that show up alongside "
        "each other, not proven causes.")
    add("- Skill suggestions are only as current as the skills list "
        "(built %s)." % (ctx.get("index_built_at") or "unknown"))
    return "\n".join(L)


def _load_episodes(path):
    data = json.load(open(path))
    return data.get("episodes", data) if isinstance(data, dict) else data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--trend", required=True)
    ap.add_argument("--habits", required=True)
    ap.add_argument("--recommendations", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--repo-name", default="your work")
    ap.add_argument("--out")
    a = ap.parse_args()
    ctx = {
        "repo_name": a.repo_name,
        "episodes": _load_episodes(a.episodes),
        "trend": json.load(open(a.trend)),
        "habits": json.load(open(a.habits)),
        "recommendations": json.load(open(a.recommendations)),
        "index_built_at": json.load(open(a.index)).get("built_at"),
    }
    md = render(ctx)
    if a.out:
        open(a.out, "w").write(md)
    print(md)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 coach/scripts/test_coach_report.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full coach test suite**

Run: `python3 -m pytest coach/scripts/ scripts/test_events.py -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add coach/scripts/coach_report.py coach/scripts/test_coach_report.py
git commit -m "feat(coach): deterministic console report joining all artifacts"
```

---

## GROUP G — End-to-end smoke

### Task G1: Manual end-to-end run on real logs

**Files:** none (verification only)

- [ ] **Step 1: Run the full pipeline on this repo's own logs**

Follow `coach/SKILL.md` end to end against `~/.claude/projects/<encoded cwd>/`
into `/tmp/coach-run/`: condense → events → gitdata → episodes → (Haiku narrate)
→ (Haiku score with `coach_scoring.md`) → `coach_aggregate.py` → `trend.py` →
`habits.py` → `recommend.py prep` → (Haiku rank) → `recommend.py finalize` →
`coach_report.py`.

- [ ] **Step 2: Verify the report reads for a non-engineer**

Confirm: plain axis names, softened band, a trend section (or the suppression
note), habits with counted evidence, skill suggestions, and the fine print.
No engineering jargon, no the prior tool terms, nothing opened in a browser.

- [ ] **Step 3: Commit any fixes found during the smoke run**

```bash
git add -A && git commit -m "fix(coach): end-to-end smoke fixes"
```

---

## Self-review notes (spec coverage)

- Spec §4 rubric → Tasks B1 (axes/bands) + B2 (prompt). ✓
- Spec §5 trend → Task C1, incl. sub-two-bucket suppression. ✓
- Spec §6 habits → Tasks A1 (skill signals), D1 (catalog), D2 (detector). ✓
- Spec §7 recommender → Tasks E1 (index/builder), E2 (prep/finalize/prompt). ✓
- Spec §8 report → Task F1. ✓
- Spec §9 interfaces → flat JSON artifacts; report is sole joiner. ✓
- Spec §10 honesty rails → coach_report fine print + correlational copy + trend suppression + index freshness. ✓
- Spec §2 "new skill, shared scripts" → Task A2 scaffold + `_shared.py`; shared scripts untouched except additive A1. ✓

**Two integration points to confirm during implementation (flagged inline):**
1. `gitdata.py` episode→session linkage key names (trend `_date_episodes`).
2. The `events.py` call site for `extract_slash_command`, and whether
   `redirect_count` exists as a signal (catalog rule degrades safely if not).
