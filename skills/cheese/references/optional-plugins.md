# Optional plugins — detect-and-degrade contract

Optional MCP servers can extend the skill stack.
They share one contract.
Detect each server at skill entry.
Use it when present.
Use the documented fallback when absent.
**Never block on absence.**

This document is the single source of truth for the contract. Every skill that references an optional plugin points here rather than duplicating the wording.

## The contract in three lines

1. **Detect** — check whether the agent's toolset exposes the capability before the first call.
   Match the capability, not one exact tool name.
   A host renames and prefixes MCP tools.
   Treat any tool whose name contains the server name and the operation as the same capability.
2. **Use** — call the tool if present; fold its output into the skill's evidence.
3. **Degrade** — use the documented fallback when the server is absent.
   Report the absence and confidence reduction once.
   Never block the skill.

## Optional MCPs

| MCP | Capability to probe | Fallback when absent | Confidence impact |
| --- | --- | --- | --- |
| hallouminate | a corpus listing operation and a semantic grounding operation | Skip wiki grounding. Note the absence once. Use diff and code evidence only. Spec discovery falls back to `resolve_slug(slug, phase_hint="specs")`, which matches names instead of semantics. | Cap at `speculating` when design rationale is central |
| milknado | a node claim and node verify operation (engine role), or a task add operation (tracker role) | Use the in-report curd decomposition. Read the manifest YAML at `.cheese/ultracook/<slug>/manifest.yaml`. Use no external task-graph backend. | No confidence impact — the decomposition itself is unchanged |

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
At phase entry, scan the agent's toolset for the capability:

- **hallouminate** — look for a tool whose name contains `hallouminate` and `list_corpora`.
- **milknado** — look for a tool whose name contains `milknado` and `todo_claim` plus one that contains `node_verify` (engine role).
  Look for a tool whose name contains `milknado` and `todo_add` for the tracker role.

Each host prefixes these names differently.
`mcp__hallouminate__list_corpora`, `mcp__plugin_hallouminate_hallouminate__list_corpora`, and `xd://mcp__hallouminate_hallouminate_list_corpora` are the same capability.
Treat any prefix as a match.
Call the tool by the exact name that the host exposes.
If the capability is present, it is available. If absent, skip and note once.

## Install

See `scripts/install.sh --help` and `README.md § Optional tools` for install instructions for each MCP. Both are opt-in — they are not in `EC_DEFAULT_MCP`.
