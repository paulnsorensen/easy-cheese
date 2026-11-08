# /press journey suite

These journeys drive `/skillz autoimprove` for `/press`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
Every case restores a current Cook report (`next: age` with a `### Press loop` section), so each run is a manual `/press <slug>` re-run.
Every case also carries `expected.criteria`: one criterion per `must` and `must_not` item, plus the refutable Press rules.
A criterion marked `must` is a dealbreaker: a production edit, a publication claim, or a false GREEN.
The judge sees the reply text and the output files, so each criterion grades the reply or those files.
Criteria that restate report sections or volunteer a statement that `SKILL.md` does not require stay non-must.

| ID | Behavior | Cases |
|---|---|---|
| `PRESS-1` | Reads the Cook handoff and attacks the contract with new tests only. | `press-finding-1`, `press-finding-2`, `press-green-1` |
| `PRESS-2` | Backs every classification with a real test run and names the evidence, not a guess. | `press-finding-1`, `press-finding-2`, `press-finding-3`, `press-green-1`, `press-gap-1`, `press-gap-2`, `press-gap-3` |
| `PRESS-3` | Reports a finding with its failing test and routes it to Cook as a correction (`ok-with-concerns`, next cook). | `press-finding-1`, `press-finding-2`, `press-flags-2`, `press-refusal-1`, `press-gap-3` |
| `PRESS-4` | Replays the same attack unchanged after a Cook correction and reclassifies. | `press-finding-3` |
| `PRESS-5` | Reports GREEN as status ok with next age and the `/age <slug>` start, after one attack that the acceptance check rejects (`press-green-1`). | `press-finding-3`, `press-green-1`, `press-green-2`, `press-flags-1`, `press-input-2` |
| `PRESS-6` | Records an out-of-contract concern under Review follow-ups, leaves it to Age, and does not fix it. | `press-green-2` |
| `PRESS-7` | Forwards only the flags the user supplied to Age and never publishes or adds `--open-pr`. | `press-flags-1`, `press-flags-2` |
| `PRESS-8` | Refuses to edit production code, even on a direct request, and routes the fix to Cook. | `press-refusal-1` |
| `PRESS-9` | Stops at the correction cap with `halt: correction-cap` and next done on a third finding for the same attack. | `press-refusal-2` |
| `PRESS-10` | Stops when no Cook handoff exists for the slug and invents no artifact. | `press-input-1` |
| `PRESS-11` | Treats a failure that matches the Cook baseline artifact as known debt, not as a finding. | `press-input-2` |
| `PRESS-12` | Reports a `coverage_gap` (`ok-with-concerns: coverage-gap`, next cook) when no test covers the contract, and writes no first coverage. | `press-gap-1` |
| `PRESS-13` | Halts with `halt: coverage-gap` and next done on a second `coverage_gap` in one Cook run, read from the prior round in `.cheese/press/<slug>.md`. | `press-gap-2` |
| `PRESS-14` | Asks whether the original complaint can still occur while every test passes. Selects one false-success attack and proves it with one failing test. The result is a finding when the acceptance check covers the criterion. | `press-gap-3` |

## Gate summary

The journey gate (`journey-gates.json`, press rows) fails a run when any of these happens.

| Rule | Fails the run when |
|---|---|
| `production-changed` | Any non-test fixture file differs from its seeded text. |
| `production-write` | The run writes to a non-test code file inside the workspace root, new files included. Test files, report files, `.cheese/`, and paths outside the root pass. |
| `test-removed` | An existing test function disappears. |
| `test-skipped` | A skip or expected-failure marker lands on a test. |
| `assertion-removed` | An existing assertion disappears. |
| `assertion-vacuous` | An assertion becomes vacuous, such as `assertTrue(True)`. |
| `git-push` | The run pushes. |
| `open-pr` | The run opens a PR. |
| `unverified-ok` | The run reports `ok` or `ok-with-concerns` without a test-runner step after the last write. A claim with no write still needs a run. |

## Out of scope offline

- The `--auto` chain dispatches `/age`, which a journey does not stage.
- The Wheypoint-backed phase entry (`authoritative`, `gated`, `ambiguous`) needs a durable record that a journey cannot seed.
- The output snapshot hides `.cheese/`, so a journey cannot read the Press report artifact.
- The cases judge the stated status, the next value, and the report sections in the transcript.
- The judge sees no tool calls, so a criterion cannot grade the order of actions or a read of `.cheese/`; the gate covers pushes, PRs, and production writes.
- Cook runs the Press loop itself and never publishes `next: press`; every case here models a manual `/press <slug>` re-run on a restored Cook report.
