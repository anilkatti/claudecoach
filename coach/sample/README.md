# Sample coach profile

`profile.json` is a **synthetic** coach profile with the exact schema the pipeline
emits (`coach/scripts/profile.py` → `build_profile`). It lets you exercise the
island's profile badge without running the full `coach_run.py` (which needs real
session transcripts and Haiku scoring).

To preview the badge on any machine, drop it where the island watches for it:

```sh
mkdir -p ~/.claude/coach
cp coach/sample/profile.json ~/.claude/coach/profile.json
```

The island's `profile_watcher` picks up the file and renders the badge
(band + overall score + trend arrow). Here that's **Solid · 7.0 · ▲** (trend up,
since `trend.overall_delta` is positive).

Numbers are illustrative only — "Haiku-scored & nondeterministic; a snapshot,
not a verdict."
