---
name: perform-actions
description: Phase-3 executor for ClaudeCoach — the DO step after /recommend-actions. Reads THIS project's actions.json and applies the recommendations the user approves, each via a doer agent for its kind: install a skill/MCP (run_command), archive an unused/duplicate capability reversibly, scaffold a skill, hand off to a config skill, and coherently reorganize context documents (CLAUDE.md/memory) for capture/trim edits. Every change is shown as a diff or command and confirmed first; removals are reversible archives, never deletes. Use after /recommend-actions, or when the user says "apply the recommendations", "perform actions", "do the reorganize", "apply the config changes". Trigger on "/perform-actions".
---

# perform-actions

The **executor** (DO) of ClaudeCoach: profile-builder senses, recommend-actions
recommends, this skill **acts** — and it is the *only* skill that touches the user's
files. It consumes the `actions.json` that /recommend-actions wrote and applies the
**approved** actions, each through a doer agent for its `apply.kind`. Run scripts from
**this skill's own directory**; pass the user's project as the first arg / `--cwd`.

## Step 0 — Consent gate (before any change)
Tell the user and wait for a yes:
> "I'll apply the approved recommendations from THIS project's actions.json (built by
> /recommend-actions). I walk them in priority order and apply only the ones you say
> yes to. Every change is shown as a diff or command first; capability removals are
> reversible archives (moved aside, never deleted) and file edits are backed up.
> Proceed?"

## Step 1 — Load actions (plumbing)
Run: `python scripts/load_actions.py "<project cwd>"`
Parse stdout JSON. If `error == "no_actions"`: tell the user there's nothing to apply
for this project and **offer to run `/recommend-actions` first** — then stop. If
`error == "bad_json"`: report the path and stop. Otherwise keep `dir`, `path`, and read
the `doc` (the actions.json itself) from `path`.

## Step 2 — Walk + route (per-action consent)
Walk `doc.actions` in `do_now` → `consider` → `fyi` order. For each action, show its
`title`, `rationale`, and `apply.preview`, then ask whether to apply it. Only on an
explicit **yes**, route by `apply.kind`:
- `run_command` → dispatch `prompts/installer.md` (`{{ACTION_JSON}}` = the action).
- `archive` → dispatch `prompts/archiver.md`.
- `scaffold_skill` → dispatch `prompts/scaffolder.md`.
- `handoff_skill` → dispatch `prompts/handoff.md`.
- `advisory` → nothing to perform; it's guidance — acknowledge it and move on.
- `edit_file` → **do not apply yet**; collect its `id` for the reorganize pass (Step 3).

After each non-`edit_file` action you handled, record the result:
`python scripts/set_status.py "<path>" <action_id> applied|skipped`
(`applied` if the doer confirmed success, `skipped` if the user declined or the doer
reported `failed`).

## Step 3 — Reorganize pass (edit_file, coherent per file)
For the approved `edit_file` ids collected in Step 2, run:
`python scripts/plan_reorg.py "<path>" <approved_id> <approved_id> …`
→ a list of `{target_path, action_ids}`, one entry per context file. For **each** group:
- Dispatch `prompts/context_reorganizer.md` (**model: opus**) with `{{TARGET_PATH}}`,
  `{{CURRENT_CONTENT}}` (read the file live, right now), and `{{ACTIONS}}` (the actions
  whose ids are in this group).
- If its output ends with a `CONFLICT:` line, show the conflict and ask the user how to
  resolve it — **do not write**; mark those ids `skipped` unless they choose to proceed.
- Otherwise write the returned content to a temp file, show the diff
  (`python scripts/apply.py diff "<target_path>" "<temp>"`), and ask to confirm. On
  **yes**: `python scripts/apply.py edit "<target_path>" "<temp>"` (backs up first),
  then mark each id `applied` via `set_status.py`. On **no**: mark them `skipped`.

## Step 4 — Summarize
Tell the user what was applied vs skipped, where backups/archives live and the exact
restore/undo commands, and the honesty rails: nothing was applied without their yes;
removals are reversible (archive, not delete); edits were backed up; doers reported real
outcomes, not assumed success.

## Honesty rails
- Only this skill mutates files, and only on explicit per-action consent.
- Reversible by construction: archive (move) + backup-before-edit; diffs shown first.
- A doer that can't confirm success → the action is `skipped` with the reason, never a
  fabricated `applied`.

## Tests
`python -m pytest scripts/` exercises the plumbing (load_actions, plan_reorg, set_status,
apply, prompts, integration).
