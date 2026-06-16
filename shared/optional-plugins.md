# Optional plugins — detect-and-degrade contract

Three optional MCP servers extend the skill stack beyond the required tilth + Context7 baseline; they share one contract: probe at skill entry, use when present, degrade to a documented fallback when absent. **Never block on absence.**

This document is the single source of truth for the contract. Every skill that references an optional plugin points here rather than duplicating the wording.

## The contract in three lines

1. **Detect** — check whether the MCP's tools appear in the agent's toolset before the first call.
2. **Use** — call the tool if present; fold its output into the skill's evidence.
3. **Degrade** — if absent, fall back as documented below; state the absence and any confidence reduction once; never hard-block the skill.

## Optional MCPs

| MCP | Key tool(s) to probe | Fallback when absent | Confidence impact |
| --- | --- | --- | --- |
| code-review-graph | `build_or_update_graph_tool`, `get_review_context_tool` | `tilth_deps` + `cheez-search kind: "callers"` for blast radius; skip cross-repo, semantic search, and architecture framing | Cap at `speculating` for cross-repo or large-architecture questions |
| hallouminate | `mcp__hallouminate__list_corpora`, `mcp__hallouminate__ground` | Skip wiki grounding; note absence once; proceed with diff + code evidence only | Cap at `speculating` when design rationale is central |
| milknado | `mcp__milknado__milknado_todo_add`, `mcp__milknado__milknado_graph_summary` | Use the in-report curd decomposition (manifest YAML in `.cheese/cheese-factory/<slug>/manifest.yaml`); no external task-graph backend | No confidence impact — the decomposition itself is unchanged |

## Reporting an unavailable optional MCP

Once per run, at the point where the tool would first be called:

```text
OPTIONAL MCP ABSENT: <name> not loaded. Falling back to <fallback>.
<Confidence note when applicable.>
```

Do not retry. Do not ask the user to install the MCP during the run. Do not silently swap to a different question.

## Probe pattern

Detection is instruction-level, not code. At the relevant phase entry, check whether the tool name is in the agent's available toolset:

- **code-review-graph** — look for `build_or_update_graph_tool` in available tools.
- **hallouminate** — look for `mcp__hallouminate__list_corpora` in available tools.
- **milknado** — look for `mcp__milknado__milknado_todo_add` in available tools.

If the tool is present, it is available. If absent, skip and note once.

## Install

See `scripts/install.sh --help` and `README.md § Optional tools` for install instructions for each MCP. All three are opt-in — they are not in `EC_DEFAULT_MCP`.
