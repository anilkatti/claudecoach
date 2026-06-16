# perform-actions

The Phase-3 **executor** (the DO step) of ClaudeCoach. After `/profile-builder` senses
and `/recommend-actions` recommends, this skill **applies** the approved actions — and
it is the only ClaudeCoach skill that changes your files.

```
profile-builder ─▶ recommend-actions ─▶ perform-actions
   SENSE              RECOMMEND             DO
 profile.json    →   actions.json     →  applies, reversibly
```

It reads `~/.claude/profiles/<slug>/actions.json`, walks it in priority order, and for
each action you approve dispatches a doer agent for its kind:
- **run_command** → installer (run + verify an install / symlink / MCP add)
- **archive** → archiver (move a capability aside, reversibly)
- **scaffold_skill** → scaffolder (hand a drafted spec to skill-creator)
- **handoff_skill** → handoff (invoke update-config / fewer-permission-prompts)
- **edit_file** → context-reorganizer (coherently apply capture/trim edits to a
  CLAUDE.md / memory file — one rewrite per file)
- **advisory** → guidance only, nothing to apply

## Install
```sh
ln -s "$PWD/skills/perform-actions" ~/.claude/skills/perform-actions
```
Requires an `actions.json` — run `/recommend-actions` first. Then `/perform-actions`.

## Privacy & safety
- The only ClaudeCoach skill that mutates files, and only on explicit per-action consent.
- Removals are reversible archives (moved aside, never deleted); edits are backed up and
  shown as a diff before writing.

## Tests
`python -m pytest skills/perform-actions/scripts/`
