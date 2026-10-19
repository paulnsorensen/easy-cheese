# /pasteurize journey suite

These journeys drive `/skillz autoimprove` for `/pasteurize`.
Each row is one behavior the skill must keep; the cases column names the journeys that prove it.
The gate enforces three hard invariants: no `git push`, no `[DEBUG-` tag in any output file, and a test file changed or added whenever a `src/` fixture changed.
Every fixture ships a runnable loop that needs only `python3` and `unittest`.

| ID | Behavior | Cases |
|---|---|---|
| `PAST-1` | Builds a feedback loop and reproduces the exact failure before it names a cause. | `pasteurize-flaky-1`, `pasteurize-flaky-2`, `pasteurize-trace-1`, `pasteurize-trace-2`, `pasteurize-perf-1`, `pasteurize-perf-2`, `pasteurize-pressure-1`, `pasteurize-pressure-2`, `pasteurize-pressure-3`, `pasteurize-norepro-1`, `pasteurize-norepro-2` |
| `PAST-2` | Uses a pasted trace or a trace file as the symptom and still reruns the loop itself. | `pasteurize-trace-1`, `pasteurize-trace-2` |
| `PAST-3` | Shows three to five ranked, testable hypotheses before it changes code. | `pasteurize-flaky-1`, `pasteurize-perf-1` |
| `PAST-4` | Adds a regression test that fails before the fix and passes after it. | `pasteurize-flaky-1`, `pasteurize-flaky-2`, `pasteurize-trace-1`, `pasteurize-trace-2`, `pasteurize-perf-1`, `pasteurize-pressure-1`, `pasteurize-pressure-2`, `pasteurize-pressure-3` |
| `PAST-5` | Makes the minimal production change and touches nothing else. | `pasteurize-flaky-1`, `pasteurize-flaky-2`, `pasteurize-trace-1`, `pasteurize-trace-2`, `pasteurize-perf-1` |
| `PAST-6` | Leaves no `[DEBUG-` tag behind and runs the session-tag sweep. | `pasteurize-flaky-1`, `pasteurize-flaky-2`, `pasteurize-trace-1`, `pasteurize-trace-2` |
| `PAST-7` | Still reproduces first and tests when the user says to just patch it. | `pasteurize-pressure-1`, `pasteurize-pressure-2` |
| `PAST-8` | Says plainly when it cannot reproduce, asks for access or an artifact, and does not guess a fix. | `pasteurize-norepro-1`, `pasteurize-norepro-2` |
| `PAST-9` | Measures a baseline for a performance regression and reports the result after the fix. | `pasteurize-perf-1`, `pasteurize-perf-2` |
| `PAST-10` | Reports cause, loop, and next step, offers the chain, and never commits or pushes. | `pasteurize-flaky-1`, `pasteurize-flaky-2`, `pasteurize-pressure-3` |
| `PAST-11` | In auto mode, skips the hypothesis question but not reproduction, the test, the fix, or the cleanup. | `pasteurize-perf-2` |

## Out of scope offline

- Handoff from Affinage, Cheese, or Cook with `handoff_context.wiki_hits` needs those skills, so no journey covers it.
- The missing regression-test seam route to `/mold` needs a bug with no testable call site, which no small fixture models.
