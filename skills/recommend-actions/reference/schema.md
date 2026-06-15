# /recommend-actions schemas

Phase-2 recommender. Consumes **profile-builder v2** output
(`~/.claude/profiles/<slug>/{project,user}.profile.json`, `schema_version: 2`)
and produces `actions.json` + `actions.html` in the same profile directory.

## Lanes (output of `load_profile.py split`)

`load_profile.py` slices the two profiles into four lanes, one per specialist:

```json
{
  "acquire":  {"project_gaps": [], "user_gaps": [], "task_archetypes": [],
               "domains": [], "tools_and_materials": [],
               "owned_capabilities": {}, "mcp_footprint": {}},
  "config":   {"context_health": {}, "friction_signals": []},
  "author":   {"friction_signals": [], "task_archetypes": [], "owned_capabilities": {}},
  "behavior": {"behavioral_signals": {}, "friction_signals": [], "habits": []}
}
```

**Field provenance.** `load_profile.py` renames each source profile's `gaps` to
`project_gaps` (from `project.profile.json`) and `user_gaps` (from `user.profile.json`),
`owned_capabilities` comes from `user.profile.json` (used for dedupe), and `mcp_footprint`
is lifted out of `user.profile.json`'s `context_health`. The lane keys above are the
output of `split_lanes`, not raw profile field names.

## Candidate action (each specialist emits a JSON array of these)

```json
{
  "family": "acquire | config | author | behavior",
  "action_type": "install_skill | add_mcp | add_plugin | trim | merge_sharpen | capture_context | automate_hook | cut_permission_friction | author_asset | adopt_practice | stop_antipattern",
  "title": "<short imperative>",
  "rationale": "<plain-English why>",
  "evidence": [{"signal": "user.friction_signals[1]", "detail": "...",
                "quote": "session:<id> \"verbatim\"", "confidence": 0.0}],
  "impact_estimate": {"kind": "tokens_saved | reexplains_avoided | qualitative",
                      "value": 0, "basis": "<provenance: profile number or k-of-n count this came from>"},
  "source": {"kind": "curated_index | live_web | local_signal",
             "ref": "capabilities_index:<name>", "url": "", "freshness": "built_at <date>"},
  "effort": "low | medium | high",
  "apply_hint": {"kind": "run_command | scaffold_skill | edit_file | handoff_skill | archive | advisory",
                 "preview": "<exact command / diff / handoff text>",
                 "handoff": "skill-creator | update-config | fewer-permission-prompts | null",
                 "reversible": true}
}
```

## Final `actions.json` (synthesizer → render → Phase 3)

```json
{
  "schema_version": 1,
  "generated_at": "<ISO8601>",
  "project_slug": "<cwd encoded: re.sub('[^a-zA-Z0-9]','-', abspath)>",
  "profile_ref": {"generated_at": "...", "stale": false, "sessions_sampled": 0},
  "indexes": {"capabilities_built_at": "...", "best_practices_built_at": "..."},
  "consent": {"network_used": false},
  "actions": [{
    "id": "capture-coa-context", "family": "config", "action_type": "capture_context",
    "priority": "do_now | consider | fyi",
    "title": "...", "rationale": "...", "evidence": [/* as above */],
    "impact_estimate": {/* as above */}, "source": {/* as above */}, "effort": "low",
    "apply": {"kind": "edit_file", "preview": "<diff>", "reversible": true,
              "handoff": null, "status": "pending | applied | skipped"}
  }],
  "not_recommended": [{"considered": "...", "why_dropped": "superseded by <id> / no source found"}],
  "disclaimer": "LLM-derived from an evidence-verified but partial sample; nondeterministic; research as fresh as the index build + any live top-up."
}
```

`apply.kind` takes the same values as `apply_hint.kind`
(`run_command | scaffold_skill | edit_file | handoff_skill | archive | advisory`); the synthesizer
resolves each candidate's `apply_hint` into the concrete `apply` block.

## Curated index schemas (written by `build_indexes.py`)

`capabilities_index.json`:
```json
{"built_at": "<ISO8601>",
 "capabilities": [{"name": "...", "kind": "skill | mcp | plugin", "source": "...",
                   "one_liner": "...", "when_to_use": "...", "tags": [], "url": "..."}]}
```

`best_practices.json`:
```json
{"built_at": "<ISO8601>",
 "practices": [{"id": "...", "principle": "...", "applies_to_signal": "<behavioral_signals key or habit>",
                "source_url": "...", "source_org": "anthropic | openai"}]}
```

`build_indexes.py` also writes a top-level `dropped: [...]` array on each index
(sources or records it skipped) so a degraded build is visible, never silent.

## Honesty rails (enforced in prompts + code)
- Every action cites a profile signal; the synthesizer drops candidates that can't re-ground.
- Never recommend a capability/practice without a real `url`/`source_url` (curated entry or verified live). No invented names.
- Habit/practice findings are correlational ("often alongside…", never "caused"), each with a counted evidence string.
- "unused" = "unused in the sampled sessions" — never "globally dead".
- Removals are reversible (archive, never delete); config edits show a diff + backup.
