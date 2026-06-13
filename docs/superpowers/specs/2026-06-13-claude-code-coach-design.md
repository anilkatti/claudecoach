# Claude Code Coach — Design

**Date:** 2026-06-13
**Status:** Approved for planning
**Supersedes:** nothing — new product alongside `the prior assessment tool`

## 1. Problem & goal

`the prior assessment tool` scores a developer's Claude Code/Codex sessions on the prior tool's
**exact, verbatim** 5-axis engineering rubric. Its axes (Execution Leverage,
Steering, Engineering Quality, Product Thinking, Planning) and anchor text are
deliberately engineering-specific and the prior tool-internal. That fidelity is the whole
point of `the prior assessment tool` and must not change.

**This product is different.** It is a **Claude Code performance coach for
everyone** — point it at anyone's JSONL session logs and tell them, in plain
language:

1. How well they are working with Claude Code (a friendly 5-axis score).
2. Whether they are improving over time.
3. Which skills they should adopt — and which skills/habits are holding them back.

Audience is **truly everyone** — people using Claude Code for writing, research,
ops, not only engineers. So nothing user-facing may use engineering jargon
(no "LOC", "numstat", "subagent dispatch", "Execution Leverage").

This document covers all four subsystems and their interfaces together, per the
explicit request to design them as one picture.

## 2. Key decisions (locked)

- **Repo strategy:** new skill, **shared scripts**. `the prior assessment tool` stays intact
  and faithful. The tool-agnostic extraction scripts are reused, not forked.
- **Rubric:** fresh plain-English axes tuned to general Claude Code use (not a
  reword of the prior tool's). Scores stay on a 1–10 scale.
- **Bands:** same numeric cut thresholds, encouraging labels.
- **Skills recommender:** Haiku **ranks a curated JSON index** (no vector DB,
  no backend). Research-backed for small short-description corpora — off-the-shelf
  embedding retrieval performs poorly on tool/skill retrieval and drags down
  downstream success (*ToolRet*, arXiv:2503.01763), while an LLM in the ranking
  loop improves it especially for irregularly-updated toolsets (arXiv:2406.17465).
- **Trend:** bucket the analyzed sessions by **ISO week** within the batch; no
  cross-run persistence in v1.
- **Audience:** zero engineering jargon in user-facing output.

## 3. Architecture overview

```
JSONL logs ──► condense.py ──► events.py(+skills) ──► gitdata.py ──► decisions.py
                                                          │
                                       narrate (Haiku) ◄──┘
                                                          │
                                                episodes.py
                                                          │
                       ┌──────────────────────────────────┼───────────────────────────┐
                       ▼                  ▼                ▼               ▼             ▼
              coach_scoring (Haiku)   trend.py        habits.py      recommend.py   (skills_index.json,
                  episodes.json       trend.json      habits.json   (Haiku ranks)    repo-shipped)
                       └──────────────────┴────────────────┴───────────────┴──────────────┘
                                                          │
                                                  coach_report.py  ──►  console report
```

**Reused unchanged** (tool-agnostic extraction): `condense.py`, `gitdata.py`,
`decisions.py`, `episodes.py`, and `events.py` (with one additive change in §6.1).

**New / rewritten** (coach-specific): `prompts/coach_scoring.md`,
`aggregate.py` axes+bands (coach copy), `scripts/trend.py`, `scripts/habits.py`
+ `reference/habit_catalog.json`, `scripts/recommend.py` +
`prompts/skill_recommender.md` + `reference/skills_index.json` +
`scripts/build_skills_index.py`, `scripts/coach_report.py`.

### 3.1 Shared-scripts layout

The tool-agnostic scripts are factored into a shared location both skills import,
so a fix to extraction benefits both products and neither drifts:

```
repo root/
  pipeline/               # shared, tool-agnostic (moved from the prior assessment tool/scripts)
    condense.py  events.py  gitdata.py  decisions.py  episodes.py
  the prior assessment tool/            # existing product (rubric + report stay faithful)
    prompts/  reference/  scripts/(aggregate, report)  SKILL.md
  claude-code-coach/      # NEW product
    prompts/  reference/  scripts/  SKILL.md
```

Exact mechanism (a shared package vs. a thin re-export) is an implementation
detail for the plan; the **contract** is: extraction code has exactly one home,
and the coach owns its rubric/trend/habits/recommender/report.

## 4. Unit — Rubric (the five plain-English axes)

`prompts/coach_scoring.md` replaces `episode_scoring.md`. Same machinery
(per-episode Haiku scoring, 1–10, axis omission when no evidence), new substance.

| Key | Display name | "What this means" (verbatim in report) |
|---|---|---|
| `outcomes` | Getting things done | Does your work with the AI actually reach finished results — or stall, loop, and get abandoned? |
| `steering` | Steering the AI | How clearly you direct it and catch it going the wrong way. |
| `quality` | Quality bar | Do you hold its output to a high standard — checking, verifying, not just accepting? |
| `planning` | Thinking ahead | Do you set up the work before diving in, scaled to how big the task is? |
| `leverage` | Working smart | Do you use the right tools, skills, and habits to get more done with less effort? |

- Each axis gets 1-2/3-4/5-6/7-8/9-10 anchors written in plain "you" language,
  framed around outcomes and habits, **never** code-specific vocabulary. The
  effort-calibration and halo-avoidance guidance from the the prior tool prompt is kept
  (it is sound and not the prior tool-specific), reworded.
- Scorer output JSON renames the human-facing fields:
  `what_happened` (was `facts`), `what_it_shows` (was `interpretation`),
  `caveat` (was `counterweight`); plus `title`, `confidence`, `scores{...}`.
- **Axis generalization note:** `leverage` replaces the prior tool's `product_thinking`
  (which is engineering-specific). `quality` generalizes "engineering quality"
  to any output (writing, analysis, code). Axis omission still applies — e.g.
  omit `outcomes`/`quality` for exploration-only sessions with no produced
  artifact.

### 4.1 Bands

Same numeric cuts as today (`aggregate.py` `BANDS`), encouraging labels:

| Score | Label |
|---|---|
| 0–4 | Getting started |
| 4–6 | Finding your footing |
| 6–8 | Solid |
| 8–9 | Strong |
| 9–10 | Exceptional |

A coach copy of `aggregate.py` carries `AXES = [outcomes, steering, quality,
planning, leverage]` and the new band labels. Rollup logic (confidence-weighted
mean per axis, then mean of axes) is unchanged.

## 5. Unit — Trend over time (`scripts/trend.py`)

- **In:** `episodes.json` (scored, with `episode_id`) + session timestamps;
  date each episode via its linked session(s) (`gitdata.json` linkage already
  exists).
- **Logic:** bucket episodes by **ISO week**. Per axis, confidence-weighted mean
  per week (reuse the rollup function). Compute first→last delta per axis and
  overall.
- **Out:** `trend.json`:
  ```json
  {
    "weeks": [{"week": "2026-W22", "axes": {"outcomes": 6.4, ...},
               "overall": 6.1, "n_episodes": 3}],
    "deltas": {"outcomes": +0.8, "...": 0, "overall": +0.5}
  }
  ```
- **Edge case (load-bearing):** if all episodes fall in a single ISO week, emit
  `{"weeks": [...one...], "deltas": null, "note": "not enough time span to show
  a trend yet"}`. The report renders the note instead of a fabricated trajectory.
  No trend claim is made on fewer than two buckets.

## 6. Unit — Habit coaching

### 6.1 `events.py` additive change (the only change to a shared script)

Detect skill usage (needed by both habits and the recommender):
- A `tool_use` block with `name == "Skill"` → `skill_invoke` event with
  `{name: inp["skill"], source: "skill_tool", timestamp}`.
- A `<command-name>...</command-name>` slash-command tag in user turns
  (already recognized in `LOCAL_COMMAND_TAGS`) → `skill_invoke` with
  `{name, source: "slash_command", timestamp}`.
- Add `skills_invoked` (deduped list + counts) to `session_signals`.

This is purely additive — existing event types and `the prior assessment tool` behavior are
unaffected.

### 6.2 `reference/habit_catalog.json` + `scripts/habits.py`

- Catalog modeled on `decision_catalog.json`. Each entry:
  `{key, label (plain English), polarity: "strength" | "holding-you-back",
    detect (rule over session_signals/events), coaching (one plain sentence)}`.
  Seed entries: vague prompts, no plan before a big change, blindly accepting
  output, thrash/rework, good course-correction, verifies before calling it
  done, runs work in parallel.
- `habits.py` evaluates the rules **deterministically** over the extracted
  signals → `habits.json`:
  `{habits: [{key, label, polarity, coaching, evidence: "<count-backed>"}]}`.
- **Framing rule:** habits are correlational. Coaching copy says "often shows up
  alongside…", never "caused". Every habit carries a counted evidence string.

## 7. Unit — Skills recommender

### 7.1 `reference/skills_index.json` (repo-shipped)

Curated `[{name, source, one_liner, when_to_use, tags}]`. `source` ∈
`{builtin, marketplace, anthropic-docs}`. Built offline by:

### 7.2 `scripts/build_skills_index.py` (build-time only, networked)

Fetches the skill marketplace + relevant Anthropic docs, normalizes to the index
schema, writes `skills_index.json`. **Network is used only at build time**; the
index ships in the repo so runtime stays local / no-backend / console-only.
The index records a `built_at` date surfaced in the report's fine print
(freshness honesty).

### 7.3 `scripts/recommend.py` + `prompts/skill_recommender.md`

- **Deterministic assembly:** input = the user's weak axes (from the rollup) +
  habit flags (`habits.json`) + skills already used (from `skills_invoked`) +
  the full `skills_index.json`.
- **Haiku ranks** via the verbatim recommender prompt → `recommendations.json`:
  ```json
  {
    "recommend":  [{"name", "why (plain)", "helps_axis"}],
    "reconsider": [{"name", "why (plain)"}]
  }
  ```
- **"Reconsider" (skills hurting them):** skills the user invokes that co-occur
  with low `outcomes`/`quality` episodes or anti-pattern habits. Framed as
  correlational, with the co-occurrence count cited. Never claims causation.

## 8. Unit — Report (`scripts/coach_report.py`)

Deterministic templating (same discipline as `report.py`: every claim a fixed
template filled with counted evidence). Joins all artifacts on `episode_id` /
axis keys. Console-only — no HTML, nothing opened in a browser.

Sections:
1. **Verdict** — softened band + overall score, strongest/weakest axis.
2. **Your five scores** — table: axis name · score · band · the plain
   "what this means" line.
3. **How you're trending** — from `trend.json` (or the not-enough-span note).
4. **What's working / What's holding you back** — from `habits.json`.
5. **Skills to try / Skills to reconsider** — from `recommendations.json`.
6. **Episode highlights** — per-episode `title` + `what_it_shows` (verbatim
   scorer reads, highest confidence first).
7. **Fine print** — Haiku-scored & nondeterministic; trend/habit/skill
   inferences are correlational; `skills_index` `built_at` date.

## 9. Inter-unit interfaces (contracts)

Each unit reads/writes one flat JSON artifact in the working dir; the report is
the only joiner. This lets each unit be built and tested independently.

| Artifact | Producer | Consumers | Key contract |
|---|---|---|---|
| `episodes.json` | coach_scoring (Haiku) | trend, recommend, report | each entry wrapped with `episode_id`; `scores` use the 5 coach keys |
| `trend.json` | `trend.py` | report | `weeks[]`, `deltas` (or `null` + `note`) |
| `habits.json` | `habits.py` | recommend, report | `habits[]` with polarity + counted evidence |
| `skills_index.json` | `build_skills_index.py` (offline) | recommend, report | `built_at`; entries `{name,source,one_liner,when_to_use,tags}` |
| `recommendations.json` | `recommend.py` (Haiku) | report | `recommend[]`, `reconsider[]` |

## 10. Honesty rails (carried over and adapted)

- Scorer is **Claude Haiku 4.5**; scoring is **nondeterministic** — re-runs vary,
  no number is presented as definitive.
- Trend, habit, and "skills hurting you" findings are **correlational**, stated
  as such, each backed by a counted evidence string. Never causal language.
- Trend is suppressed below two ISO-week buckets.
- `skills_index.json` freshness (`built_at`) is shown; recommendations are only
  as current as the last index build.
- The report is **deterministic given the artifacts** (same inputs → byte-identical
  output) and **console-only**.

## 11. Out of scope (explicit, for later specs)

- Cross-run persisted history / long-term progress tracking (v1 trend is
  within-batch only).
- Vector / embedding retrieval for the recommender (revisit only if the index
  grows beyond what Haiku can rank in one pass).
- Auto-refresh of `skills_index.json` (manual rebuild in v1).
- Codex CLI support for the coach (the shared pipeline already supports it; the
  coach rubric/report can adopt it in a follow-up if desired).

## 12. Open risks

- **Skills-index acquisition** depends on the marketplace/docs being fetchable
  and stably structured; `build_skills_index.py` must degrade gracefully (skip a
  source, log what was dropped) rather than ship a half-built index silently.
- **Index size vs. single-pass ranking:** if the corpus outgrows one Haiku
  context, fall back to a deterministic tag-prefilter before ranking (still no
  vector DB). Flagged, not built, in v1.
- **Few-session reports** produce noisy scores and no trend; the report must say
  so plainly rather than over-claim.
