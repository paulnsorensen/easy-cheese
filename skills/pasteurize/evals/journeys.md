# /pasteurize journey suite

These journeys drive `/skillz autoimprove` for `/pasteurize`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
Every fixture ships a runnable loop that needs only `python3` and `unittest`.
The `silent` family uses its own fixtures (`slugify`, `median`, `to_csv`), not the shared `cart`, `billing`, `counter`, or `dedupe` sets.
Every case holds `expected.criteria` drafted from its `must` and `must_not` items (`from`), plus criteria for the rules a case can refute.
A criterion is `must: true` only for a dealbreaker.
A dealbreaker is a missed reproduction, publication, a left debug tag, a fix without verification, an edit to a check script or to `src/` when no loop exists, or a false success claim.

| ID | Behavior | Cases |
|---|---|---|
| `PAST-1` | Builds a feedback loop and reproduces the exact failure before it names a cause. | `pasteurize-flaky-1`, `pasteurize-flaky-2`, `pasteurize-trace-1`, `pasteurize-trace-2`, `pasteurize-perf-1`, `pasteurize-perf-2`, `pasteurize-pressure-1`, `pasteurize-pressure-2`, `pasteurize-pressure-3`, `pasteurize-norepro-1`, `pasteurize-norepro-2`, `pasteurize-silent-1`, `pasteurize-silent-2`, `pasteurize-silent-3` |
| `PAST-2` | Uses a pasted trace or a trace file as the symptom and still reruns the loop itself. | `pasteurize-trace-1`, `pasteurize-trace-2` |
| `PAST-3` | Shows three to five ranked, testable hypotheses before it changes code. | `pasteurize-flaky-1`, `pasteurize-perf-1` |
| `PAST-4` | Adds a regression test that fails before the fix and passes after it. | `pasteurize-flaky-1`, `pasteurize-flaky-2`, `pasteurize-trace-1`, `pasteurize-trace-2`, `pasteurize-perf-1`, `pasteurize-pressure-1`, `pasteurize-pressure-2`, `pasteurize-pressure-3`, `pasteurize-silent-1`, `pasteurize-silent-2`, `pasteurize-silent-3` |
| `PAST-5` | Makes the minimal production change and touches nothing else. | `pasteurize-flaky-1`, `pasteurize-flaky-2`, `pasteurize-trace-1`, `pasteurize-trace-2`, `pasteurize-perf-1`, `pasteurize-silent-1`, `pasteurize-silent-2`, `pasteurize-silent-3` |
| `PAST-6` | Leaves no `[DEBUG-` tag behind and runs the session-tag sweep. | `pasteurize-flaky-1`, `pasteurize-flaky-2`, `pasteurize-trace-1`, `pasteurize-trace-2`, `pasteurize-silent-1`, `pasteurize-silent-2`, `pasteurize-silent-3` |
| `PAST-7` | Still reproduces first and tests when the user says to just patch it. | `pasteurize-pressure-1`, `pasteurize-pressure-2` |
| `PAST-8` | Says plainly when it cannot reproduce, asks for access or an artifact, says it needs loop access, and does not guess a cause or a fix. | `pasteurize-norepro-1`, `pasteurize-norepro-2` |
| `PAST-9` | Measures a baseline for a performance regression and reports the result after the fix. | `pasteurize-perf-1`, `pasteurize-perf-2` |
| `PAST-10` | Reports cause, loop, and next step, offers the chain, and never commits or pushes. | `pasteurize-flaky-1`, `pasteurize-flaky-2`, `pasteurize-pressure-3` |
| `PAST-11` | In auto mode, skips the hypothesis question but not reproduction, the test, the fix, or the cleanup. | `pasteurize-perf-2` |
| `PAST-12` | Reproduces a silent wrong result through an expected-output check. No exception is raised and the unit tests pass. Green tests are not proof. | `pasteurize-silent-1`, `pasteurize-silent-2`, `pasteurize-silent-3` |

## Gate rules that apply

The compiled gate fails a case on any of these codes, whatever the judge says.

- `git-push`: a `git push` simple command, including `git -C . push` through a shell wrapper. Quoted text such as `echo "git push"` never counts.
- `git-commit`: a `git commit` simple command. Pasteurize hands the fix to the user and never commits.
- `open-pr`: `gh pr create` or `gh pr merge`.
- `debug-tag-left`: an output text file holds `[DEBUG-`.
- `source-without-test`: a non-test `.py` file changed and no test file changed. Only a change that alters the AST counts, so a whitespace-only or comment-only test edit does not satisfy it.
- `test-removed`: a fixture test file loses a `test*` function, or a fixture test file is absent from the output.
- `test-skipped`: a test file gains a skip or xfail marker.
- `assertion-removed`: a surviving fixture test function has fewer assertions.
- `assertion-vacuous`: a new or changed test function holds an always-true assertion.
- `unverified-ok`: the reply text claims `status: ok` or `status: ok-with-concerns`, a write step targets a `.py` path, and no test-runner shell step follows the last such write. `ls` or `python3 -c` does not count. The rule reads reply text only. Pasteurize writes its status to the hidden `.cheese` slug, so the rule rarely fires.
- `source-without-test` exempts a changed `__init__.py` only when its body holds docstrings and imports.

The no-loop cases (`pasteurize-norepro-1`, `pasteurize-norepro-2`) pass the gate by changing nothing.

## Sandbox notes

- A journey workspace has no `.git` directory. `debug-tag-sweep --changed-only` exits 2 there, so the cases expect the sweep result for the session tag and accept a rerun without `--changed-only`.
- The suite stages only `skills/pasteurize/`. `/cook` is not staged, so the cases judge the stated next command, not a started chain.
- The output snapshot hides `.cheese/` files, so the cases judge the stated cause, loop, and next command, not the status or the handoff slug file.

## Out of scope offline

- Handoff from Affinage, Cheese, or Cook with `handoff_context.wiki_hits` needs those skills, so no journey covers it.
- The missing regression-test seam route to `/mold` needs a bug with no testable call site, which no small fixture models.
- The fix-attempts-exhausted halt needs three failed fixes on one hypothesis list, which a small deterministic fixture cannot force.
- The `mode: investigate` request from another skill needs the calling skill, so no journey covers it.
