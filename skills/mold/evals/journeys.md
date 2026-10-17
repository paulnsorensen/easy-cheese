# /mold journey suite

These journeys drive `/skillz autoimprove` for `/mold`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces that Mold writes no source file, changes no fixture code file, and makes no git commit or push.

| ID | Behavior | Cases |
|---|---|---|
| `MOLD-1` | A small, clear ask gets a Quick tier with a one-line reason and no long interview. | `mold-mini-1`, `mold-mini-2`, `mold-mini-3`, `mold-forks-1`, `mold-forks-2`, `mold-boundary-2`, `mold-boundary-3`, `mold-recover-3` |
| `MOLD-2` | The spec is saved at the resolver path and passes strict validation. | `mold-mini-1`, `mold-mini-2`, `mold-mini-3`, `mold-forks-1`, `mold-forks-2`, `mold-forks-3`, `mold-recover-1`, `mold-recover-2`, `mold-recover-3`, `mold-boundary-1`, `mold-boundary-2`, `mold-boundary-3` |
| `MOLD-3` | Every goal has an acceptance criterion, and non-goals are listed. | `mold-mini-1`, `mold-mini-2`, `mold-mini-3`, `mold-forks-1`, `mold-forks-2`, `mold-forks-3`, `mold-recover-2`, `mold-recover-3` |
| `MOLD-4` | Consequential forks are asked, one at a time, as lettered options with a fork card, never settled silently. | `mold-forks-1`, `mold-forks-2`, `mold-forks-3`, `mold-recover-1` |
| `MOLD-5` | Explain more re-asks the same fork with new context and does not guess a choice. | `mold-forks-3` |
| `MOLD-6` | Minor calls are decided by the agent and logged, not put to the user. | `mold-mini-2`, `mold-forks-1`, `mold-forks-2`, `mold-recover-2` |
| `MOLD-7` | A confused user or a request for less depth makes Mold step back, explain plainly, and cut depth. | `mold-recover-1`, `mold-recover-2` |
| `MOLD-8` | A vague idea gets one narrowing question about the pain, not a list of forks. | `mold-recover-3` |
| `MOLD-9` | A saved spec or a general approval is not a Cook request; Cook needs an explicit choice. | `mold-mini-3`, `mold-boundary-1`, `mold-boundary-3` |
| `MOLD-10` | An explicit request to cook hands off to Cook with the exact spec path; Mold does not implement. | `mold-boundary-2` |
| `MOLD-11` | Mold refuses to write production code and points to Cook. | `mold-boundary-1` |

## Out of scope offline

- Wiki grounding through hallouminate needs the MCP server, which the journey sandbox lacks. The journeys accept `hallouminate: absent`.
- The fresh-context taste test and planner dispatch need sub-agents, which the journey tools lack.
