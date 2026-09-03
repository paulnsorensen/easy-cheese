# Optional plugins — detect-and-degrade contract

Optional MCP servers can extend the skill stack.
They share one contract.
Detect each server at skill entry.
Use it when present.
Use the documented fallback when absent.
**Never block on absence.**

This document is the single source of truth for the contract. Every skill that references an optional plugin points here rather than duplicating the wording.

## The contract in three lines

1. **Detect** — check whether the MCP's tools appear in the agent's toolset before the first call.
2. **Use** — call the tool if present; fold its output into the skill's evidence.
3. **Degrade** — use the documented fallback when the server is absent.
   Report the absence and confidence reduction once.
   Never block the skill.

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

Do not retry.
Do not ask the user to install the MCP during the run.
Do not replace it with a different question.

## Probe pattern

Detection is an instruction, not code.
At phase entry, check whether the agent's toolset contains the tool name:

- **hallouminate** — look for `mcp__hallouminate__list_corpora` in available tools.
- **milknado** — look for `mcp__milknado__milknado_todo_claim` + `mcp__milknado__milknado_node_verify` (engine role) or `mcp__milknado__milknado_todo_add` (tracker role) in available tools.

If the tool is present, it is available. If absent, skip and note once.

## Install

See `scripts/install.sh --help` and `README.md § Optional tools` for install instructions for each MCP. Both are opt-in — they are not in `EC_DEFAULT_MCP`.
