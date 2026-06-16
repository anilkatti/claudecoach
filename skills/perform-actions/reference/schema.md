# perform-actions — input contract

This skill consumes the `actions.json` that `/recommend-actions` writes to
`~/.claude/profiles/<slug>/actions.json` and applies the approved actions. It does not
produce that file; it reads, applies, and writes back `apply.status`.

## actions.json (fields this skill reads/writes)
```json
{
  "actions": [{
    "id": "<kebab>", "priority": "do_now | consider | fyi",
    "title": "...", "rationale": "...",
    "apply": {
      "kind": "run_command | scaffold_skill | edit_file | handoff_skill | archive | advisory",
      "preview": "<command / diff / path / handoff text>",
      "target_path": "<absolute path of the context file — REQUIRED for edit_file>",
      "handoff": "skill-creator | update-config | fewer-permission-prompts | null",
      "reversible": true,
      "status": "pending | applied | skipped"
    }
  }]
}
```

## Routing — `apply.kind` → doer
| kind           | doer                | effect |
|----------------|---------------------|--------|
| run_command    | installer           | run + verify the command |
| archive        | archiver            | `apply.py archive` (reversible) |
| scaffold_skill | scaffolder          | invoke `skill-creator` |
| handoff_skill  | handoff             | invoke the named skill |
| edit_file      | context-reorganizer | coherent rewrite of `target_path`, batched per file |
| advisory       | — (none)            | guidance only |

## Reorganize grouping
`plan_reorg.py` filters approved actions to `apply.kind == "edit_file"` and groups by
`apply.target_path`, so all approved edits to one CLAUDE.md/memory file become a single
coherent reorganizer pass. An `edit_file` action with no `target_path` cannot be grouped
and is skipped (the orchestrator warns).

## Honesty rails
- Apply only on explicit per-action consent; nothing by default.
- Reversible: archive (move, never delete) + backup-before-edit; diffs shown first.
- A doer reports real outcomes; an unverifiable action is `skipped`, never `applied`.
