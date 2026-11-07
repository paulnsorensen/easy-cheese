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
- `tests-fail` runs unittest in a copy of `output/` when Python changed and `output/tests/` exists.
- `unverified-ok` fails a `status: ok` claim after a Python write with no later shell step.

## Judge evidence

The judge sees the request, the brief, the case files, the transcript, the output files, and the reference.
It does not see the tool trace.
The transcript keeps only the last message of each agent turn, and the harness asks for that message as JSON in `result_json`.
The output files skip every path part that starts with a dot, so the judge never sees `.cheese/`.
A progress message inside a turn (the contract, a red run, the gate output) therefore reaches only the gate, not the judge.

A `must` criterion zeroes the case below level 3, so it must name evidence the judge has: a property of the output files compared with the case files, or a claim in a reply.
The gate owns "the tests ran in this conversation": `unverified-ok` needs a shell step after the last Python write, and `tests-fail` runs the suite on `output/`.
The judge then checks with `success-matches-output` or `check-matches-output` that the output files do not contradict a claim in a reply.
These criteria zero a case only on a contradiction, such as a claimed fix that the code lacks.
A claimed check that leaves no file, such as an ad-hoc command, is not a contradiction; the gate and, later, the trace grade it.

### Trace-only criteria

These criteria grade behavior that only the tool trace shows.
They stay optional, so a reasonable run loses mean level on them but never scores 0.
Tighten each one, or make it `must`, when the judge receives the full tool trace.

| Case | Criterion | Trace evidence to check |
|---|---|---|
| `cook-tdd-1` | `contract-before-code` | The contract message comes before the first Python write. |
| `cook-tdd-1` | `acceptance-coverage` | A unittest run fails before `bulk_total` exists. |
| `cook-tdd-1`, `cook-tdd-2`, `cook-press-1`, `cook-press-2` | `success-matches-output` | Also require a gate run after the last write, with its output. |
| `cook-tdd-2` | `fast-path-contract`, `regression-coverage` | The contract message comes before the edit, and the new test fails first. |
| `cook-prototype-1` | `restore-and-record-base`, `prototype-branch`, `plan-before-spike` | `bash restore-repo.sh` and the branch switch come before the first edit, and a plan message comes before each spike. |
| `cook-prototype-1` | `check-matches-output` | Also require the check command in the trace of that round. |
| `cook-press-1` | `contract-before-code`, `red-first` | The contract message and a red unittest run come before `textkit/slug.py` is written. |
| `cook-press-2` | `reads-finding-and-shows-red` | `bash restore-state.sh`, a read of `.cheese/press/withdraw.md`, and a red gate run come before the edit. |
| every case | `no-publish`, `no-publish-dispatch` | No `git push`, `gh pr create`, or `/age` or `/plate` start before the user picks one. The gate already fails a push or a PR. |

## Out of scope offline

- The fan pathway (curds, waves, sub-agent coders) needs the `Agent` tool, which a journey does not grant.
- The `--auto` chain and `--open-pr` publication dispatch later phases and need `gh` and a remote.
- The prototype Stabilize route hands off to `/mold`, which the journey does not stage.
- The Press loop runs inline because the journey agent has no sub-agent tool. Press itself is not staged, so the attack choice is judged from the transcript only.
- The `.cheese/` handoff files are hidden from the judge, so the stated status and `next:` in the transcript carry the handoff evidence.
- The `coverage_gap` and correction-cap halts of the Press loop are not covered.
- The prototype spike asks for a unittest check so the `source-without-test` gate passes.
