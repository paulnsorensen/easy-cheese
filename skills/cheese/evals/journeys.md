# /cheese journey suite

These journeys drive `/skillz autoimprove` for `/cheese`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
Every case carries `expected.criteria`: one criterion per `must` and `must_not` item, plus the router rules that the case can refute.
The deterministic gate is `scripts/journey_gates/cheese.py`, compiled into `autoimprove.json`; it reads Claude and Codex traces.

| ID | Behavior | Cases |
|---|---|---|
| `CHEESE-1` | Routes each input shape to the correct target skill. | `cheese-route-1`, `cheese-route-2`, `cheese-route-3`, `cheese-route-4`, `cheese-route-5`, `cheese-route-6`, `cheese-clarify-1`, `cheese-clarify-2`, `cheese-safe-1`, `cheese-safe-2`, `cheese-continue-3`, `cheese-guard-1`, `cheese-guard-2`, `cheese-steer-1`, `cheese-steer-2` |
| `CHEESE-2` | Announces Intent, Reason, and Target before it dispatches. | `cheese-route-1`, `cheese-route-2`, `cheese-route-3`, `cheese-route-4` |
| `CHEESE-3` | Ends the routing block with one well-formed route receipt that matches its fast or escalated path. | `cheese-route-1`, `cheese-route-2`, `cheese-route-3`, `cheese-route-4`, `cheese-route-5`, `cheese-route-6`, `cheese-clarify-1`, `cheese-clarify-2`, `cheese-safe-1`, `cheese-continue-1`, `cheese-guard-2`, `cheese-steer-1`, `cheese-steer-2` |
| `CHEESE-4` | Asks exactly one clarifying question on vague input, dispatches nothing, and re-routes on the answer. | `cheese-clarify-1`, `cheese-clarify-2` |
| `CHEESE-5` | Under --safe, offers a gate with the recommended target first and Stop last, and waits for the user. | `cheese-safe-1`, `cheese-safe-2` |
| `CHEESE-6` | Refuses to edit files, run tests, commit, or push itself, and routes the work. | `cheese-guard-1`, `cheese-guard-2` |
| `CHEESE-7` | Reports honestly when the target skill cannot load, and does not do the target's work. | `cheese-route-1`, `cheese-route-2`, `cheese-route-6`, `cheese-safe-2`, `cheese-continue-1`, `cheese-continue-2`, `cheese-guard-1` |
| `CHEESE-8` | Resumes through the wheypoint resolve path, stops on gated or missing handoffs, and never infers --auto. | `cheese-continue-1`, `cheese-continue-2`, `cheese-continue-3` |
| `CHEESE-9` | Adapts to a live user correction of scope and routes again. | `cheese-steer-1` |
| `CHEESE-10` | Surfaces a rejected-direction record before a mold dispatch and asks whether to proceed. | `cheese-steer-2` |
| `CHEESE-11` | Routes an explicit no-writes thinking request to culture. | `cheese-route-5` |

## Gate summary

The journey gate fails a run when any of these happens.

| Rule | Fails the run when |
|---|---|
| `edit-tool` | A file tool writes a visible path. Hidden state (`.cheese/`) and scratch space are exempt. |
| `shell-redirect-write` | A shell redirect or `tee` writes a visible path. |
| `shell-file-write` | `touch`, `rm`, `mv`, `cp`, `mkdir`, `ln`, `truncate`, or an in-place `sed`/`perl` targets a visible path. |
| `fixture-changed` | A fixture file differs from its seeded text or is gone. |
| `new-output-file` | The output holds a visible file that no fixture seeded. |
| `test-runner` | The run starts a test suite (`pytest`, `python -m unittest`, `just check`, `npm test`, `cargo test`, and similar). |
| `git-commit`, `git-push`, `open-pr` | The run commits, pushes, or opens a PR. |
| `receipt-format` | A `route:` line does not match `route: intent=<intent> target=<skill> path=<fast\|escalated> probes=<n>`. |
| `receipt-path-probes` | A receipt pairs `path=fast` with a nonzero probe count. `path=escalated probes=0` passes, because an input off the fast path stays escalated. |
| `no-trace` | The trace has no agent turn. |

## Out of scope offline

- Dispatch into the target skill: only `/cheese` is staged, so the journeys grade the routing decision and receipt, not the downstream work.
- PR and issue context probes through `gh`: the sandbox has no network and no `gh`.
- Wiki grounding through hallouminate: the server is absent, so the escalated wiki-hit lines are not covered.
- `--reground`: it needs a git history window and the `/culture` pass, which the sandbox lacks.
- Restore scripts are user-authorized sandbox setup for hidden state. The continue cases grade an honest stop, because `/wheypoint resolve` is not staged.
