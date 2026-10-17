# /cheese journey suite

These journeys drive `/skillz autoimprove` for `/cheese`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces that the router never writes a non-hidden file, runs a test suite, commits, or pushes, and that every route receipt is well formed.

| ID | Behavior | Cases |
|---|---|---|
| `CHEESE-1` | Routes each input shape to the correct target skill. | `cheese-route-1`, `cheese-route-2`, `cheese-route-3`, `cheese-route-4`, `cheese-route-5`, `cheese-route-6`, `cheese-clarify-1`, `cheese-clarify-2`, `cheese-safe-1`, `cheese-safe-2`, `cheese-continue-2`, `cheese-continue-3`, `cheese-guard-1`, `cheese-guard-2`, `cheese-steer-1`, `cheese-steer-2` |
| `CHEESE-2` | Announces Intent, Reason, and Target before it dispatches. | `cheese-route-1`, `cheese-route-2`, `cheese-route-3`, `cheese-route-4` |
| `CHEESE-3` | Ends the routing block with one well-formed route receipt that matches its fast or escalated path. | `cheese-route-1`, `cheese-route-2`, `cheese-route-3`, `cheese-route-4`, `cheese-route-5`, `cheese-route-6`, `cheese-clarify-1`, `cheese-clarify-2`, `cheese-safe-1`, `cheese-continue-1`, `cheese-continue-2`, `cheese-guard-2`, `cheese-steer-1`, `cheese-steer-2` |
| `CHEESE-4` | Asks exactly one clarifying question on vague input, dispatches nothing, and re-routes on the answer. | `cheese-clarify-1`, `cheese-clarify-2` |
| `CHEESE-5` | Under --safe, offers a gate with the recommended target first and Stop last, and waits for the user. | `cheese-safe-1`, `cheese-safe-2` |
| `CHEESE-6` | Refuses to edit files, run tests, commit, or push itself, and routes the work. | `cheese-guard-1`, `cheese-guard-2` |
| `CHEESE-7` | Reports honestly when the target skill cannot load, and does not do the target's work. | `cheese-route-1`, `cheese-route-2`, `cheese-route-6`, `cheese-safe-2`, `cheese-continue-1`, `cheese-guard-1` |
| `CHEESE-8` | Resumes through the wheypoint resolve path, stops on gated or missing handoffs, and never infers --auto. | `cheese-continue-1`, `cheese-continue-2`, `cheese-continue-3` |
| `CHEESE-9` | Adapts to a live user correction of scope and routes again. | `cheese-steer-1` |
| `CHEESE-10` | Surfaces a rejected-direction record before a mold dispatch and asks whether to proceed. | `cheese-steer-2` |
| `CHEESE-11` | Routes an explicit no-writes thinking request to culture. | `cheese-route-5` |

## Out of scope offline

- Dispatch into the target skill: only `/cheese` is staged, so the journeys grade the routing decision and receipt, not the downstream work.
- PR and issue context probes through `gh`: the sandbox has no network and no `gh`.
- Wiki grounding through hallouminate: the server is absent, so the escalated wiki-hit lines are not covered.
- `--reground`: it needs a git history window and the `/culture` pass, which the sandbox lacks.
