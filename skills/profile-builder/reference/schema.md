# Profile schemas

Two artifacts are written to `~/.claude/profiles/<slug>/`. Both are
evidence-grounded: every domain/tech/strength/gap cites a `session:<id>` and/or a
verbatim quote. Phase 1 covers the **current project only**.

## `project.profile.json` — what this repo is & what work happens in it

```json
{
  "schema_version": 1,
  "kind": "project",
  "generated_at": "<ISO8601>",
  "project": {"slug": "...", "root": "<cwd>", "git_remote": "...",
              "worktrees_merged": ["..."]},
  "summary": "2-3 plain-English sentences on what this repo is and the work done here",
  "domains":         [{"name": "...", "weight": 0.0, "evidence": ["session:<id> \"...\""]}],
  "tech_stack":      [{"name": "...", "weight": 0.0, "evidence": ["..."]}],
  "task_archetypes": [{"name": "...", "weight": 0.0, "evidence": ["..."]}],
  "project_relevant_capabilities": [{"name": "...", "source": "repo|personal|plugin",
                                     "used_here": true}],
  "gaps": [{"need": "...", "rationale": "...", "evidence": ["..."]}],
  "provenance": {"sessions_total": 0, "sessions_sampled": 0,
                 "sampling": "recency-stratified", "seed": 0,
                 "skipped_short": 0, "too_short_chosen": 0, "extraction_failures": 0,
                 "models": {"per_session": "claude-haiku-4-5-20251001",
                            "synthesis": "claude-opus-4-8"}},
  "disclaimer": "LLM-derived from a recency-stratified sample; evidence-grounded but nondeterministic."
}
```

## `user.profile.json` — how this person works, observed in this project only

```json
{
  "schema_version": 1,
  "kind": "user",
  "generated_at": "<ISO8601>",
  "observed_in": {"project_slug": "...",
                  "note": "behavior observed within this project only; cross-project merge deferred"},
  "summary": "2-3 plain-English sentences on how this person works",
  "working_style":      [{"preference": "...", "evidence": ["..."]}],
  "behavioral_signals": {
    "prompting":    {"value": "...", "evidence": ["..."]},
    "planning":     {"value": "...", "evidence": ["..."]},
    "verification": {"value": "...", "evidence": ["..."]},
    "steering":     {"value": "...", "evidence": ["..."]},
    "leverage":     {"value": "...", "evidence": ["..."]}
  },
  "habits": [{"label": "...", "polarity": "strength|holding-back",
              "evidence": "k of n sampled sessions", "detail": "..."}],
  "owned_capabilities": {"skills": [{"name": "...", "description": "...", "source": "..."}],
                         "commands": [], "agents": [], "mcp_servers": [{"name": "...", "source": "..."}]},
  "skill_usage": [{"name": "...", "sessions_seen": 0}],
  "strengths": [{"area": "...", "evidence": ["..."]}],
  "gaps":      [{"area": "...", "rationale": "...", "evidence": ["..."]}],
  "provenance": {"...": "same shape as project.profile"},
  "disclaimer": "LLM-derived from a recency-stratified sample; evidence-grounded but nondeterministic."
}
```

`strengths[]` and `gaps[]` are the hooks a Phase-2 recommender keys off.
`profile.md` is a human-readable rendering of both files.
