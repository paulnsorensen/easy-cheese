# /culture journey suite

These journeys drive `/skillz autoimprove` for `/culture`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces that Culture writes no source file, changes no fixture code file, writes no spec, and makes no git commit or push.

| ID | Behavior | Cases |
|---|---|---|
| `CULT-1` | Restates the question in one sentence, names a false premise, and models the problem without code or a spec. | `culture-model-1`, `culture-model-2`, `culture-model-3`, `culture-fork-1`, `culture-altitude-1`, `culture-altitude-3` |
| `CULT-2` | Tags options with blast radius or confidence, compares explanations, and steelmans the rejected option. | `culture-model-1`, `culture-model-2`, `culture-fork-2`, `culture-altitude-2` |
| `CULT-3` | Raises each consequential fork conversationally and one at a time, and never bundles forks. | `culture-model-3`, `culture-fork-1`, `culture-fork-2`, `culture-record-1` |
| `CULT-4` | Decides small calls itself and logs the alternative instead of asking. | `culture-fork-1`, `culture-fork-2` |
| `CULT-5` | Records a decision or idea only when the user asks, at the tracked fallback path, with one loud fallback line. | `culture-record-1`, `culture-record-2`, `culture-record-3` |
| `CULT-6` | Does not record a passing thought the user did not settle. | `culture-record-2` |
| `CULT-7` | Shifts altitude when the user asks to zoom out or make it concrete, and states its reading first. | `culture-altitude-1`, `culture-altitude-2` |
| `CULT-8` | Stays within the agreed scope and asks before it widens; no rabbit holes. | `culture-model-2`, `culture-altitude-3` |
| `CULT-9` | Refuses code, specs, commits, and PRs, and routes to /cook or /mold. | `culture-boundary-1`, `culture-boundary-2` |
| `CULT-10` | The user declares the session over; Culture then states the handoff with a next value and never declares convergence itself. | `culture-model-1`, `culture-record-3` |
| `CULT-11` | On a no-writes request, keeps the ledger in the conversation and writes no file. | `culture-model-3` |

## Out of scope offline

- The session wheypoint needs the `/wheypoint` skill, which the journey sandbox does not stage. The journeys require only that Culture states the handoff.
- Wiki records and ADRs through hallouminate need the MCP server. The journeys cover the tracked fallback path.
