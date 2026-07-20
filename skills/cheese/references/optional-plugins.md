# Optional plugins — detect-and-degrade contract

Optional MCP servers can extend the skill stack beyond host-native backends; they share one contract: probe at skill entry, use when present, degrade to a documented fallback when absent. **Never block on absence.**

This document is the single source of truth for the contract. Every skill that references an optional plugin points here rather than duplicating the wording.

## The contract in three lines

1. **Detect** — check whether the MCP's tools appear in the agent's toolset before the first call.
2. **Use** — call the tool if present; fold its output into the skill's evidence.
3. **Degrade** — if absent, fall back as documented below; state the absence and any confidence reduction once; never hard-block the skill.

## Optional MCPs

| MCP | Key tool(s) to probe | Fallback when absent | Confidence impact |
| --- | --- | --- | --- |
| hallouminate | `mcp__hallouminate__list_corpora`, `mcp__hallouminate__ground` | Skip wiki grounding; note absence once; proceed with diff + code evidence only. Spec-discovery specifically falls back to `resolve_slug(slug, phase_hint="specs")` (name-based instead of semantic) | Cap at `speculating` when design rationale is central |
| milknado | `mcp__milknado__milknado_todo_claim` + `mcp__milknado__milknado_node_verify` (engine) or `mcp__milknado__milknado_todo_add` (tracker) | Use the in-report curd decomposition (manifest YAML in `.cheese/ultracook/<slug>/manifest.yaml`); no external task-graph backend | No confidence impact — the decomposition itself is unchanged |

## Reporting an unavailable optional MCP

Once per run, at the point where the tool would first be called:

```text
OPTIONAL MCP ABSENT: <name> not loaded. Falling back to <fallback>.
<Confidence note when applicable.>
```

Do not retry. Do not ask the user to install the MCP during the run. Do not silently swap to a different question.

## Probe pattern

Detection is instruction-level, not code. At the relevant phase entry, check whether the tool name is in the agent's available toolset:

- **hallouminate** — look for `mcp__hallouminate__list_corpora` in available tools.
- **milknado** — look for `mcp__milknado__milknado_todo_claim` + `mcp__milknado__milknado_node_verify` (engine role) or `mcp__milknado__milknado_todo_add` (tracker role) in available tools.

If the tool is present, it is available. If absent, skip and note once.

## Install

See `scripts/install.sh --help` and `README.md § Optional tools` for install instructions for each MCP. Both are opt-in — they are not in `EC_DEFAULT_MCP`.
