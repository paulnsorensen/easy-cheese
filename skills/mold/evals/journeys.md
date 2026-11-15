# /mold journey suite

These journeys drive `/skillz autoimprove` for `/mold`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate fails a run when Mold writes a source file or creates a new source file.
The gate also fails a run when Mold changes a fixture code file, makes a git commit, pushes, or opens a PR.
Each case also carries EARS `expected.criteria`. Only the dealbreakers are `must`: production code, starting Cook without an explicit request, and a commit or push.

| ID | Behavior | Cases |
|---|---|---|
| `MOLD-1` | A small, clear ask gets a tier announcement with a one-line reason and no long interview. The cases grade the announcement, not the Quick tier name. | `mold-mini-1`, `mold-mini-2`, `mold-mini-3`, `mold-boundary-2`, `mold-boundary-3` |
| `MOLD-2` | The spec is saved at the resolver path and passes strict validation. | `mold-mini-1`, `mold-mini-2`, `mold-mini-3`, `mold-forks-1`, `mold-forks-2`, `mold-forks-3`, `mold-recover-1`, `mold-recover-2`, `mold-recover-3`, `mold-boundary-1`, `mold-boundary-2`, `mold-boundary-3`, `mold-leverage-1`, `mold-leverage-2`, `mold-leverage-3`, `mold-hidden-1`, `mold-hidden-2`, `mold-coverage-1`, `mold-coverage-2`, `mold-shift-1`, `mold-shift-2`, `mold-premise-1`, `mold-premise-2` |
| `MOLD-3` | Every goal has an acceptance criterion, and non-goals are listed. | `mold-mini-1`, `mold-mini-2`, `mold-mini-3`, `mold-forks-1`, `mold-forks-2`, `mold-forks-3`, `mold-recover-2`, `mold-recover-3`, `mold-leverage-1`, `mold-leverage-2`, `mold-leverage-3`, `mold-coverage-1`, `mold-coverage-2` |
| `MOLD-4` | Mold asks each consequential fork one at a time, as lettered options with a fork card, and never settles it silently. | `mold-forks-1`, `mold-forks-2`, `mold-forks-3`, `mold-leverage-1`, `mold-leverage-2`, `mold-leverage-3`, `mold-hidden-1`, `mold-hidden-2`, `mold-coverage-1`, `mold-coverage-2`, `mold-shift-1`, `mold-shift-2`, `mold-premise-1`, `mold-premise-2` |
| `MOLD-5` | Explain more re-asks the same fork with new context and does not guess a choice. | `mold-forks-3` |
| `MOLD-6` | The agent decides minor calls and logs them, and does not put them to the user. | `mold-mini-2`, `mold-forks-1`, `mold-forks-2`, `mold-recover-2`, `mold-hidden-1`, `mold-hidden-2`, `mold-coverage-1`, `mold-coverage-2`, `mold-shift-1`, `mold-premise-1`, `mold-premise-2` |
| `MOLD-7` | A confused user or a request for less depth makes Mold step back, explain plainly, and cut depth. | `mold-recover-1`, `mold-recover-2` |
| `MOLD-8` | A vague idea gets one narrowing question about the pain, not a list of forks. | `mold-recover-3` |
| `MOLD-9` | A saved spec or a general approval is not a Cook request; Cook needs an explicit choice. | `mold-mini-3`, `mold-boundary-1`, `mold-boundary-3` |
| `MOLD-10` | An explicit request to cook hands off to Cook with the exact spec path; Mold does not implement. | `mold-boundary-2` |
| `MOLD-11` | Mold refuses to write production code and points to Cook. | `mold-boundary-1` |
| `MOLD-12` | A fired leverage trigger rules Quick out, so Mold names the reason and asks the consequential fork. | `mold-forks-1`, `mold-forks-2`, `mold-leverage-1`, `mold-leverage-2`, `mold-leverage-3`, `mold-hidden-1`, `mold-hidden-2`, `mold-coverage-1`, `mold-coverage-2` |
| `MOLD-13` | Mold finds a fired leverage trigger that only the code shows, such as a reader that a deletion breaks or an external parser of a payload. No request or document names the trigger. | `mold-hidden-1`, `mold-hidden-2` |
| `MOLD-14` | Each asked part reaches an acceptance criterion or a recorded deferral, and Mold never presents a partial spec as the whole request. | `mold-coverage-1`, `mold-coverage-2` |
| `MOLD-15` | A new constraint or a correction in the middle of the dialogue reopens the affected decision or goal through the user. Mold does not keep a stale decision or change it silently. | `mold-shift-1`, `mold-shift-2` |
| `MOLD-16` | Mold corrects a false premise or a prerequisite that the repository cannot meet, with code evidence, before it shapes the solution. | `mold-premise-1`, `mold-premise-2` |

## Out of scope offline

- Wiki grounding through hallouminate needs the MCP server, which the journey sandbox lacks. The journeys accept `hallouminate: absent`.
- The fresh-context taste test and planner dispatch need sub-agents, which the journey tools lack.
- The leverage trigger list lives in the cheese routing policy, which the sandbox does not stage. The leverage cases rely on the trigger categories that the Mold description and tier reference name.
- Quick tier entry needs Cook's standalone fast-path check in `cook/SKILL.md`, which the sandbox does not stage. The cases grade a tier announcement, not the literal Quick tier.
- The judge cannot see the `.cheese/` spec file. Spec-content criteria rest on what the agent reports in its replies.
