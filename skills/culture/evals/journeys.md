# /culture journey suite

These journeys drive `/skillz autoimprove` for `/culture`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
Every case carries `expected.criteria`: one criterion per `must` and `must_not` item, plus the Culture rules that the case can refute.
The deterministic gate is `scripts/journey_gates/culture.py`, compiled into `autoimprove.json`; it reads Claude and Codex traces.

| ID | Behavior | Cases |
|---|---|---|
| `CULT-1` | Restates the question in one sentence, names a false premise, and models the problem without code or a spec. | `culture-model-1`, `culture-model-2`, `culture-model-3`, `culture-fork-1`, `culture-altitude-1`, `culture-altitude-3` |
| `CULT-2` | Tags options with blast radius or confidence, compares explanations, and steelmans the rejected option. | `culture-model-1`, `culture-model-2`, `culture-fork-2`, `culture-altitude-2` |
| `CULT-3` | Raises each consequential fork conversationally and one at a time, and never bundles forks. | `culture-fork-1`, `culture-fork-2` |
| `CULT-4` | Decides small calls itself and logs the alternative instead of asking. | `culture-fork-1`, `culture-fork-2` |
| `CULT-5` | Records a decision or idea only when the user asks, at the tracked fallback path, with one loud fallback line. | `culture-record-1`, `culture-record-2` |
| `CULT-6` | Does not record a passing thought the user did not settle. | `culture-record-2` |
| `CULT-7` | Shifts altitude when the user asks to zoom out or make it concrete, and states its reading first. | `culture-altitude-1`, `culture-altitude-2` |
| `CULT-8` | Stays within the agreed scope, states what it left unchecked, and asks before it widens; no rabbit holes. | `culture-model-2`, `culture-altitude-3` |
| `CULT-9` | Refuses code, specs, commits, and PRs, and routes to /cook or /mold. | `culture-boundary-1`, `culture-boundary-2` |
| `CULT-10` | The user declares the session over; Culture then states the handoff with a next value and never declares convergence itself. | `culture-model-1`, `culture-record-3` |
| `CULT-11` | On a no-writes request, keeps the ledger in the conversation and writes no file. | `culture-model-3` |

## Gate summary

The journey gate fails a run when any of these happens.

| Rule | Fails the run when |
|---|---|
| `write-tool-source-file` | A file tool writes a code file. |
| `bash-writes-source-file` | A shell redirect or `tee` writes a code file. |
| `new-source-file` | The output holds a code file that no fixture seeded. |
| `fixture-source-changed` | A fixture code file differs from its seeded text or is gone. |
| `spec-written-by-tool` | A file tool writes a `specs/*.md` path. |
| `spec-written-by-bash` | A shell command writes a `specs/*.md` path or runs a Mold spec command. |
| `spec-written` | The output holds a new Markdown file with Mold spec frontmatter. |
| `git-commit`, `git-push`, `open-pr` | The run commits, pushes, or opens a PR. |
| `no-trace` | The trace has no agent turn. |

## Out of scope offline

- The session wheypoint needs the `/wheypoint` skill, which the journey sandbox does not stage. The journeys require only that Culture states the handoff.
- Wiki records and ADRs through hallouminate need the MCP server. The journeys cover the tracked fallback path.
