# Press area review

## Verdict

**reject**

The review found two blockers, two high findings, two medium findings, and three low findings.
The focused Press tests report 63 passes.
Three behavioral probes confirm the handoff and telemetry defects.
Security, encapsulation, not-invented-here, and efficiency have no independent findings.

## Blocker

- <certain> **[correctness:blocker] Press cannot publish or parse its documented handoff.** `skills/press/SKILL.md:116-137` maps `Continue` to `next: press`. It also puts `action:` and `telemetry:` before the orientation. `src/easy_cheese/shared/write_handoff_artifact.py:125-151` rejects the undeclared `press -> press` transition. `src/easy_cheese/shared/handoff.py:83-160` treats `action:` as the orientation and drops `telemetry:`. `skills/cheese/SKILL.md:120-122` expects `continue: press-corrective-cook`, not `action: continue`. The handoff probe returned exit code 3 and parsed `action: dispatch` as the orientation. **Fix:** Define one machine-readable Press continuation. Put the consumed Cook report in `artifact:`. Put Press-only fields in the report body.
- <certain> **[spec:blocker] Press has no contract for flags that Cook sends.** `skills/cook/SKILL.md:195-207` invokes `/press <slug> --auto --open-pr`. `skills/cook/references/auto-mode.md:23-35,116-138` requires a Press auto-mode contract. `skills/cheese/references/handoff-gate.md:180-191` requires the chain to preserve publication flags. No Press prose contains `--auto` or `--open-pr`. `skills/press/SKILL.md:145-153` always opens an interactive Age gate. **Fix:** Add Press input and auto-mode sections. Preserve `--auto` and `--open-pr` in the Age dispatch. Honor the no-chain override separately.

## High

- <certain> **[telemetry:high] The boundary audit accepts non-test metadata changes.** `skills/press/SKILL.md:18,76-84,157-161` limits Press writes to tests and test support. `src/easy_cheese/shared/fanout/press_telemetry.py:61-67,90-92,260-266` treats all metadata as boundary-safe. `tests/fanout/python/test_press_telemetry.py:137-142` classifies `pyproject.toml` as metadata. A bundle probe reported `boundary_consistent: true` after that change. **Fix:** Compare changed paths with approved test and fixture paths. Mark every other changed path as inconsistent. Include every offending path in the record.
- <certain> **[spec:high] Out-of-contract behavior has no route action.** `skills/press/references/gap-analysis.md:15-18,81-87` requires an Age follow-up and prohibits a Press continuation. `skills/press/SKILL.md:108-110` names `ok-with-concerns`, but lines 130-143 give it no router row. `src/easy_cheese/shared/fanout/press_route.py:10-16,74-87` has no matching outcome. An agent must select an unrelated outcome. **Fix:** Add an explicit out-of-contract outcome. Dispatch Age with `ok-with-concerns` and the recorded concern.

## Medium

- <certain> **[spec:medium] The command summary omits the Age dispatch.** `src/easy_cheese/skills/press/commands.py:10-18` says the route only continues or stops. `skills/press/references/commands.md:5-8` publishes the same incomplete purpose. `src/easy_cheese/shared/fanout/press_route.py:79-80` also returns `Dispatch("/age")`. **Fix:** Name Continue, Age dispatch, and Stop in the command summary. Regenerate the command reference and bundle once.
- <certain> **[spec:medium] The third-RED text gives two different dispositions.** `skills/press/references/gap-analysis.md:68-75` calls third-RED evidence ready for review. `skills/press/SKILL.md:134-143` maps the same result to `next: done` and reserves Age for GREEN. **Fix:** Call the third-RED result ready for terminal reporting. State that it does not dispatch Age.

## Low

- <certain> **[spec:low] Press names the retired no-chain owner.** `skills/press/SKILL.md:112` says Ultracook sets the directive. `skills/ultracook/SKILL.md:8-23` only redirects to Cook. `skills/cook/references/auto-mode.md:122-138` assigns the directive to Cook's fan pathway. **Fix:** Test for the no-chain directive itself. Do not test for the retired source name.
- <certain> **[deslop:low] Press uses an unapproved metaphor.** `skills/press/SKILL.md:166` says, "Fear is the curd-killer." The phrase does not state a technical rule. **Fix:** Delete the metaphor.
- <certain> **[deslop:low] Gap analysis uses undefined abbreviations.** `skills/press/references/gap-analysis.md:55` uses `P1`, `P2`, and `P3`. The area does not define these terms. **Fix:** Use `attempt 1`, `attempt 2`, and `attempt 3`.

## Simplifications

- Keep one route truth table in `references/gap-analysis.md`.
- Make `SKILL.md` summarize the route and link to that table.
- Use the canonical handoff writer and parser.
- Keep Press-only fields in the report body.
- Compare changes with approved test paths instead of file suffixes.
- Remove old readiness labels after the route supports concerns.
- Keep the static command manifest because its targets live in shared code.
- Do not add a Press-local handoff parser.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| press -> shared `Command`, `dispatch` | ok | The imports exist at `bundle_commands.py:20-24,138-154`. The bundle lists both commands. |
| press -> shared `press-route` | broken | The route lacks an out-of-contract action at `press_route.py:10-16,74-87`. |
| press -> shared `press-telemetry` | broken | The helper accepts metadata changes at `press_telemetry.py:61-67,260-266`. |
| press -> cook | broken | `Continue` exists, but the canonical writer rejects `next: press`. |
| press -> age | broken | Age accepts the dispatch and flags, but Press drops `--auto` and `--open-pr`. |
| press -> cheese | broken | Press emits fields that `handoff.py:83-160` does not parse. |
| press -> hard-cheese | ok | `skills/press/SKILL.md:153` forwards `--hard` through Age. |
| ultracook -> press | broken | Ultracook now redirects to Cook at `skills/ultracook/SKILL.md:8-23`. |
| cook fan pathway -> press | ok | The active no-chain directive exists at `skills/cook/references/auto-mode.md:116-138`. |
| build -> press | ok | The bundle help lists `press-route` and `press-telemetry`. The route smoke test dispatches Age. |

## STE100 status

not compliant

- `skills/press/SKILL.md:166` uses an unapproved metaphor.
- `skills/press/references/gap-analysis.md:55` uses three undefined abbreviations.
- `skills/press/references/commands.md` is compliant.
- `skills/press/references/telemetry.md` is compliant.

## Follow-ups

- Cure every blocker and high finding before approval.
- Update the dependency map to name Cook as the no-chain owner.
