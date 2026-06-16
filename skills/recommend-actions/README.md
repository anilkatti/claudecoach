# recommend-actions

The Phase-2 **coach** for ClaudeCoach. It reads the evidence-verified profile that
`/profile-builder` produced and turns its signals into prioritized, opt-in-apply
recommendations across four families:

- **acquire** — public skills / MCP servers / plugins that fill a real gap
- **config** — trim bloat, capture recurring context, automate a step
- **author** — turn a recurring pattern into the lightest viable reusable asset
- **behavior** — adopt good habits / stop anti-patterns, cited to Anthropic/OpenAI

It **recommends; it does not act without consent.** Read-only by default; each action
is applied only on explicit per-action approval. Output: `actions.html` (a browser
report matching `profile.html`) + `actions.json` in `~/.claude/profiles/<slug>/`.

## How it works

```
profiles ─▶ load_profile.py ─▶ 4 lanes ─┬─ doctor(config) · smith(author) · coach(behavior)  (opus, parallel) ─┐
                                         │                                                                       │
                                         └─ acquire: cache fresh? ─▶ reuse cache                                │
                                                                   : capability_scout (opus, live)  ─────────────┤
                                                                                                                 │ candidate actions
                                                                                           action_synthesizer (opus) ─▶ actions.json
                                                                                                                 │
                                                                                                         render.py ─▶ actions.html + console
                                                                                                                 │
                                                                                          hand off to /perform-actions (applies, reversibly)
```

Capability recommendations come from a **live, profile-scoped web lookup** that
`capability_scout` performs and that is **cached per project** (so re-runs stay
offline). The **best-practices** index (`reference/best_practices.json`) remains
repo-shipped, refreshed offline by `build_indexes.py`.

## Install
```sh
ln -s "$PWD/skills/recommend-actions" ~/.claude/skills/recommend-actions
```
Requires an existing profile — run `/profile-builder` first. Then `/recommend-actions`.

## Privacy
- Reads only the local profile JSON (already scrubbed by profile-builder).
- Network is used only for optional live top-up, consented up front.
- Nothing is modified until you approve a specific action; removals are reversible.

## Tests
```
python -m pytest skills/recommend-actions/scripts/
```
