# /cook journey suite

These journeys drive `/skillz autoimprove` for `/cook`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces the rules listed under Gate rules below.

| ID | Behavior | Cases |
|---|---|---|
| `COOK-1` | Prints a contract (behavior, non-goals, scope, gate, and a shape-check block or skip line) before any code. | `cook-tdd-1`, `cook-tdd-2`, `cook-scope-2`, `cook-press-1` |
| `COOK-2` | Adds first acceptance coverage that rejects the original defect for behavior work. | `cook-tdd-1`, `cook-tdd-2`, `cook-stop-3`, `cook-press-1` |
| `COOK-3` | Meets every acceptance criterion and shows the real gate output before it claims status ok. | `cook-tdd-1`, `cook-tdd-2`, `cook-stop-3`, `cook-scope-1`, `cook-scope-2`, `cook-handoff-1`, `cook-press-1`, `cook-press-2` |
| `COOK-4` | Refuses a spec with `execution_holds` and writes no code, even when asked for a stub. | `cook-stop-1` |
| `COOK-5` | Shows a false premise before any code and does not bend the code to satisfy it literally. | `cook-stop-2` |
| `COOK-6` | Asks about a design decision the spec does not answer, then follows the answer. | `cook-stop-3` |
| `COOK-7` | Honors a user scope cut or a correction in the middle of the run. | `cook-scope-1`, `cook-scope-2` |
| `COOK-8` | Adds no scope beyond the accepted contract and lists adjacent issues as follow-ups. | `cook-scope-1`, `cook-prototype-1`, `cook-handoff-2`, `cook-press-3` |
| `COOK-9` | In prototype mode, runs plan, spike, and check rounds, offers the menu, and waits for the user. | `cook-prototype-1`, `cook-prototype-2` |
| `COOK-10` | In prototype mode, discards only after an explicit yes, then restores the base and keeps the log. | `cook-prototype-2` |
| `COOK-11` | Writes the handoff report with `next: age` and the four-option menu (Review the change, Plate it, Checkpoint & stop, Stop) with no Press option, and dispatches nothing before the user selects. | `cook-handoff-1`, `cook-handoff-2`, `cook-press-2`, `cook-press-3` |
| `COOK-12` | Never weakens an existing test and never publishes without permission. | `cook-tdd-1`, `cook-scope-1`, `cook-press-1`, `cook-press-2` |
| `COOK-13` | For behavior work, runs the Press loop automatically and inline with `topology: inline`, `degraded: true`, and one round outcome stated in the reply (the `### Press loop` section is hidden from the judge); skips it for non-behavior work. | `cook-tdd-1`, `cook-tdd-2`, `cook-stop-3`, `cook-scope-1`, `cook-handoff-1`, `cook-press-1`, `cook-press-2`, `cook-press-3` |
| `COOK-14` | Fixes a Press finding with a scoped correction, replays the attack, and gives `next: age` only after the loop is green. `cook-press-2` is a deterministic correction entry: a restore script seeds the Cook and Press reports, the attack test fails on the fixture tree, and the expected run changes only production code. | `cook-press-1`, `cook-press-2` |

## Gate rules

- `git-push` and `open-pr` fail every case that publishes.
- `hold-violated` fails a run that writes Python under a spec hold.
- `test-removed`, `test-skipped`, `assertion-removed`, and `assertion-vacuous` fail a run that weakens an existing test.
- `source-without-test` fails a run that changes non-test Python without a test-file change.
- `tests-fail` runs unittest in a copy of `output/` when Python changed and `output/tests/` exists. All unittest runs share one 8 s deadline.
- `hold-violated` counts only Python written inside the workspace root.
- `unverified-ok` fails a `status: ok` claim after a Python write with no later test-runner step (a runner such as `pytest`, `python3 -m unittest`, `just`, or a script run; `ls` does not count).

## Out of scope offline

- The fan pathway (curds, waves, sub-agent coders) needs the `Agent` tool, which a journey does not grant.
- The `--auto` chain and `--open-pr` publication dispatch later phases and need `gh` and a remote.
- The prototype Stabilize route hands off to `/mold`, which the journey does not stage.
- The Press loop runs inline because the journey agent has no sub-agent tool. Press itself is not staged, so the attack choice is judged from the transcript only.
- The `.cheese/` handoff files are hidden from the judge, so the stated status and `next:` in the transcript carry the handoff evidence.
- The `coverage_gap` and correction-cap halts of the Press loop are not covered.
- The prototype spike asks for a unittest check so the `source-without-test` gate passes.
