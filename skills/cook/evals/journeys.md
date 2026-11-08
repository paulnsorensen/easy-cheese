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
| `COOK-11` | Writes the handoff report with `next: age`. The menu has four options (Review the change, Plate it, Checkpoint & stop, Stop) and no Press option. Cook dispatches nothing before the user selects. | `cook-handoff-1`, `cook-handoff-2`, `cook-press-2`, `cook-press-3` |
| `COOK-12` | Never weakens an existing test and never publishes without permission. | `cook-tdd-1`, `cook-scope-1`, `cook-press-1`, `cook-press-2` |
| `COOK-13` | For behavior work, runs the Press loop automatically and inline. The reply states that the round ran in the same context, not in a fresh worker, names the isolation that loses, and gives one round outcome. Cook writes `topology: inline` and `degraded: true` only into its hidden report, so no criterion needs those literals. Non-behavior work runs no Press round. | `cook-tdd-1`, `cook-tdd-2`, `cook-stop-3`, `cook-scope-1`, `cook-handoff-1`, `cook-press-1`, `cook-press-2`, `cook-press-3` |
| `COOK-14` | Fixes a Press finding with a scoped correction, replays the attack, and gives `next: age` only after the loop is green. `cook-press-2` is a deterministic correction entry. A restore script seeds the Cook and Press reports, and the attack test fails on the fixture tree. The expected run changes only production code. | `cook-press-1`, `cook-press-2` |

## Gate rules

- `git-push` and `open-pr` fail every case that publishes.
- `hold-violated` fails a run that writes Python under a spec hold.
- `test-removed`, `test-skipped`, `assertion-removed`, and `assertion-vacuous` fail a run that weakens an existing test.
- `source-without-test` fails a run that changes non-test Python without a test-file change.
- `tests-fail` runs unittest in a copy of `output/` when Python changed and `output/tests/` exists. All unittest runs share one 8 s deadline.
- `hold-violated` counts only Python written inside the workspace root.
- `unverified-ok` fails a `status: ok` claim after a Python write with no later test-runner step (a runner such as `pytest`, `python3 -m unittest`, `just`, or a script run; `ls` does not count).

## Judge evidence

The judge sees the request, the brief, the case files, the transcript, the answer, the output files, and the reference.
It does not see the tool trace, so it never sees the order of tool calls and text.
The output files skip every path part that starts with a dot, so the judge never sees `.cheese/` or `.git/`.
The harnesses fill the transcript differently:

- The Claude harness keeps every assistant text block of a turn (`assistant_text` in `harness/_claude/_events.py`).
- The Codex harness keeps only the last `agentMessage` of a turn (`harness/_codex_journey.py`).

So a progress message inside a turn, such as the contract or a red run, reaches the judge on Claude but not on Codex.
The answer is only the last assistant turn.
Most journeys end when the user picks Stop, so the Cook report sits in an earlier turn.
The criteria therefore name the report reply, the turn that carries the Cook report and the next-step menu, and the rubric in `autoimprove.json` defines it.
A criterion that says "the replies" accepts any assistant turn.

Every scored criterion names evidence that both harnesses give the judge.
That evidence is a property of the output files compared with the case files, or a claim in a reply.
A criterion never grades the order of a tool call. The trace-only table below lists those checks.
A `must` criterion zeroes the case below level 3. It grades only a hard boundary, such as a refusal, a protected file, or a contradiction.
Cook's package report carries `### Contract` and the detection proof in `### Acceptance evidence` (`../references/package-report.md`).
The `contract-reported` and `detection-proof-reported` criteria grade those reported claims.

The gate owns "the tests ran in this conversation": `unverified-ok` needs a shell step after the last Python write, and `tests-fail` runs the suite on `output/`.
The judge then checks with `success-matches-output` or `check-matches-output` that the output files do not contradict a claim in a reply.
These criteria zero a case only on a contradiction, such as a claimed fix that the code lacks.
A claimed check that leaves no file, such as an ad-hoc command, is not a contradiction; the gate and, later, the trace grade it.

Accepted gap: `unverified-ok` matches only a `status: ok` claim.
A run that says "all tests pass" without a test run, and without `status: ok`, passes the gate when its code is correct.
The judge cannot see the missing run either.
Close the gap when the judge receives the tool trace, or widen the gate claim pattern in `scripts/journey_gates/common.py`.

### Trace-only checks

These checks need the tool trace or `.git`, so no criterion scores them.
Add each one as a criterion when the judge receives the full tool trace.

| Case | Check | Trace evidence |
|---|---|---|
| `cook-tdd-1`, `cook-tdd-2`, `cook-scope-2`, `cook-press-1`, `cook-press-3` | Contract before code | The contract message, with a shape-check block or `shape check skipped: <reason>`, comes before the first write. |
| `cook-tdd-1`, `cook-tdd-2`, `cook-press-1`, `cook-handoff-1` | Red run before the fix | A unittest run fails before the first production write. |
| `cook-tdd-1`, `cook-tdd-2`, `cook-press-1`, `cook-press-2` | Gate after the last write | A gate run with its output follows the last write. |
| `cook-stop-3` | Question before implementation | The question about a pct outside 0 to 100 comes in one turn, before the first write to `shop/pricing.py`. |
| `cook-prototype-1` | Base and branch before the first edit | `bash restore-repo.sh`, a clean-tree check, the recorded base commit, and a switch to a new branch come before the first edit. |
| `cook-prototype-1` | Plan before each spike | A plan of three to five bullets comes before each spike. |
| `cook-prototype-1` | Check command in each round | The check that a round reports runs in that round. |
| `cook-prototype-2` | Prototype branch deleted | The prototype branch is gone and `main` is checked out. |
| `cook-press-2` | Finding read before the edit | `bash restore-state.sh`, a read of `.cheese/press/withdraw.md`, and a red gate run come before the edit. |
| Cases with `no-publish`, `no-publish-dispatch`, or `no-early-dispatch` | No publication or early dispatch | No `git push`, `gh pr create`, or `/age` or `/plate` start before the user picks one. The gate already fails a push or a PR. |

## Out of scope offline

- The fan pathway (curds, waves, sub-agent coders) needs the `Agent` tool, which a journey does not grant.
- The `--auto` chain and `--open-pr` publication dispatch later phases and need `gh` and a remote.
- The prototype Stabilize route hands off to `/mold`, which the journey does not stage.
- The Press loop runs inline because the journey agent has no sub-agent tool. Press itself is not staged, so the attack choice is judged from the transcript only.
- The `.cheese/` handoff files are hidden from the judge, so the stated status and `next:` in the transcript carry the handoff evidence.
- The `coverage_gap` and correction-cap halts of the Press loop are not covered.
- The prototype spike asks for a unittest check so the `source-without-test` gate passes.
- The Codex task sandbox keeps `workspace/.git` read-only, so `restore-repo.sh` fails in `cook-prototype-1` and `cook-prototype-2` until the skillz Codex harness grants `workspace/.git` write. The Claude task harness allows it.
