# Capability-discovery sources & config-hygiene levers

**Verified 2026-06-26 by live fetch.** These endpoints, keys, and figures **drift** —
**re-verify** against the linked live docs before asserting any of them in a recommendation.
Star/listing counts measure **visibility, not adoption**; triangulate, never trust a single
star count.

## A. Adoption sources a live scout can survey (scoped to the profile's domains)

| Source | URL | Signal | Notes |
|---|---|---|---|
| Official MCP Registry | https://registry.modelcontextprotocol.io | canonical identity (name/repo/remotes) | listing != adoption; path `/v0` vs `/v0.1` unconfirmed — verify live |
| PulseMCP | https://www.pulsemcp.com/servers (`api.pulsemcp.com/v0.1/servers`) | **real usage** — est. visitors/week | best adoption proxy; open-vs-keyed access unconfirmed |
| Glama | https://glama.ai/mcp/servers | **quality grade A–F** + weekly downloads + stars | second real-usage proxy |
| Anthropic plugin marketplace | https://github.com/anthropics/claude-plugins-official | official Claude-Code plugin feed (`marketplace.json`) | only Claude-Code-scoped feed |
| GitHub stars | `api.github.com/repos/{owner}/{repo}` | `stargazers_count` + `pushed_at` (freshness) | visibility only; pair with `pushed_at` |
| awesome-lists | `punkpeye/awesome-mcp-servers`, `hesreallyhim/awesome-claude-code` | curated breadth | staleness varies |

**Triangulation rule:** prefer a capability with a real-usage proxy (PulseMCP visitors /
Glama downloads-or-grade) AND recent `pushed_at` AND official/maintained status. A high star
count alone is **visibility, not adoption**.

## B. Config-hygiene levers (verified against code.claude.com/docs 2026-06-26 — re-verify; keys drift)

- **MCP is deferred by default.** Tool schemas load via tool search; "adding more MCP servers
  has minimal impact on your context window" (code.claude.com/docs/en/mcp). MCP footprint is
  **not** a context hog. `alwaysLoad: true` opts a server into upfront cost.
- **Skills are the always-on tax.** Each skill's name+description loads every turn (budget
  ~1% of context; least-used descriptions dropped first; ~1,536-char cap per skill) —
  code.claude.com/docs/en/skills.
- `disable-model-invocation: true` — SKILL.md frontmatter; removes the description from
  context, keeps `/name`. The cost lever for a dormant-but-wanted standalone skill.
- `skillOverrides` — `.claude/settings.local.json`; states `on | name-only |
  user-invocable-only | off` (absent = `on`). **Plugin skills are exempt.** Use to suppress a
  team/repo skill for yourself, local-only.
- `paths:` — SKILL.md frontmatter; path-scope a skill so it only loads where relevant.
- `user-invocable: false` is **not** a cost lever (the description stays in context).
- **CLAUDE.md / memory:** target **< 200 lines** per CLAUDE.md; bloat makes Claude *ignore*
  instructions (code.claude.com/docs/en/memory, /best-practices). MEMORY.md loads first 200
  lines / 25KB. Per-line test: "would removing this cause a mistake? if not, cut it."
- **Dead-weight vs dormant test:** run a representative prompt with the skill available and
  again disabled; unchanged output = dead weight, degraded = load-bearing. `/doctor` shows
  which descriptions are dropped/shortened.
- **Team vs personal:** repo `.claude/skills`, `.mcp.json`, project `CLAUDE.md` are shared —
  don't delete; suppress for yourself via `skillOverrides` (local). Personal = `~/.claude/...`
  — the user's to prune.
