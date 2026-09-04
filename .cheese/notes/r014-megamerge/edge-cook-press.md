# Cook to Press Edge Review

## State

broken

Cook can write the initial Press handoff.
Press cannot return a corrective action that Cook can consume.
Press also lacks Cook's automatic flag contract.

## Evidence

### Calls, imports, commands, and files

- Cook dispatches `/press` for behavior work (`skills/cook/SKILL.md:69-72,188-207`).
- Cook's auto route sends `--auto` and adds `--open-pr` (`skills/cook/references/auto-mode.md:23-35`).
- Cook exposes `phase-decision`, `read-handoff-slug`, and `write-handoff-artifact` (`src/easy_cheese/skills/cook/commands.py:35-39,140-151`).
- Press exposes only `press-route` and `press-telemetry` (`src/easy_cheese/skills/press/commands.py:9-20`).
- The Press CLI is the only production caller of `press_route` (`src/easy_cheese/shared/fanout/press_route_cli.py:10-35`).
- Press emits four attempt files and one report (`skills/press/SKILL.md:44-51,94-101`).
- Corrective Cook prose defines scope and test preservation only (`skills/cook/SKILL.md:20-28`; `skills/cook/references/tdd-loop.md:28-34`).
- Cook defines no correction action, retry count, attack reference, or telemetry input.

### Initial Cook handoff

Cook and Press declare the same `CurdResult` phase payload (`skills/cook/phase-contract.yaml:5-16`; `skills/press/phase-contract.yaml:5-10`).
The shared writer validates that route before it writes (`src/easy_cheese/shared/write_handoff_artifact.py:125-165`).

| Item | Cook producer | Press consumer | State |
| --- | --- | --- | --- |
| `status` | Required canonical string | Shared parser reads the string | ok |
| `next` | Required string; behavior uses `press` | Press enters after `next: press` | ok |
| `artifact` | Required CLI string; empty is valid | Press does not define its meaning | broken |
| `taste_test` | Optional string; absence is valid | Press does not name this field | untested |
| `durable_flags` | Optional string; Cook defaults to `none` | Press output omits this field | broken |
| `baseline` | Optional string; Cook defaults to `none` | Press reads and preserves this field | ok |
| orientation | Required non-empty string | Shared parser returns this string | ok |
| phase payload | `CurdResult` | Declared as `CurdResult`, but not validated | broken |

Cook defines the handoff fields at `skills/cook/SKILL.md:131-184`.
Press reads the Cook handoff and baseline at `skills/press/SKILL.md:86-101`.
Press never resolves or validates a `CurdResult` artifact.
The successful round-trip test uses an empty Cook artifact (`tests/shared/python/test_handoff_roundtrip_integration.py:268-299`).

### Corrective Press result

The route request requires exactly `outcome` and `repair_cycles` (`src/easy_cheese/shared/fanout/press_route_cli.py:12-35`).
`outcome` is a closed string enum (`src/easy_cheese/shared/fanout/press_route.py:10-16,50-62`).
`repair_cycles` is a non-Boolean integer from zero through two (`src/easy_cheese/shared/fanout/press_route.py:43-47,65-71`).
The request has no field defaults.
Missing, extra, or invalid values return a command error (`tests/fanout/python/test_press_route.py:54-76,109-155`).

| Item | Press producer | Cook consumer | State |
| --- | --- | --- | --- |
| `action` | `continue`, `dispatch`, or `stop` | No Cook input accepts it | broken |
| `reason` | `press-corrective-cook` by default | No Cook input accepts it | broken |
| `repair_cycles` | Required integer in the Press request | Corrective Cook has no matching field | broken |
| attack evidence | Candidate and route files | Corrective Cook has no matching field | broken |
| `telemetry` | Required report path | Corrective Cook has no matching field | broken |
| `status` and `next` | `ok` and `press` for continuation | Cook reads both through `phase-decision` | broken |

Press creates `Continue` for repair cycles zero and one (`src/easy_cheese/shared/fanout/press_route.py:74-84`).
The CLI serializes it as `action: continue` and `reason: press-corrective-cook` (`src/easy_cheese/shared/fanout/press_route_cli.py:15-35`).
Press maps that result to `status: ok`, `next: press`, and `action: continue` (`skills/press/SKILL.md:114-143`).

The canonical parser accepts only `taste_test`, `durable_flags`, and `baseline` (`src/easy_cheese/shared/handoff.py:83-160`).
It treats `action: continue` as the orientation.
It ignores the later `telemetry:` and orientation lines.

The canonical writer rejects `press -> press`.
Press declares only `press -> age` (`skills/press/phase-contract.yaml:5-10`).
The writer returns exit code 3 for the documented continuation.

Cook's `phase-decision` accepts `status`, optional `next`, a table, and a retry count (`src/easy_cheese/shared/fanout/phase_decision.py:296-331`).
It only uses `next` for Age and terminal decisions (`src/easy_cheese/shared/fanout/phase_decision.py:200-271`).
It sends an `ok` Press result to Age, even when `next` is `press`.
The focused probe returned `action: spawn` and `next_phase: age`.

### Flags and no-chain control

Cook defines `--auto`, `--hard`, and `--open-pr` (`skills/cook/SKILL.md:38-45`).
Press only tells the operator to pass `--hard` to Age (`skills/press/SKILL.md:145-153`).
Press defines no `--auto` or `--open-pr` input.
Press also defines no automatic Age route.

Cook adds `--open-pr` during auto mode without checking the original input (`skills/cook/references/auto-mode.md:23-28`).
Press cannot preserve either flag because its skill contract does not accept them.

Cook's fan pathway sends an explicit no-chain directive (`skills/cook/references/auto-mode.md:106-138`).
Press checks only a retired Ultracook owner (`skills/press/SKILL.md:108-112`).

### Tests and probes

- Press route tests cover action selection and invalid request values (`tests/fanout/python/test_press_route.py:19-76,79-155`).
- Shared tests cover only Cook-to-Press entry and Press-to-Age success (`tests/shared/python/test_handoff_roundtrip_integration.py:209-326`).
- Cook tests require every `ok` Press result to spawn Age (`tests/fanout/python/test_phase_decision.py:24-36`).
- Post-merge tests require the same unconditional Age route (`tests/fanout/python/test_phase_decision_tables.py:154-169`).
- No test joins `Continue` to corrective Cook.
- No test writes and parses the documented `action:` and `telemetry:` fields.
- No test verifies `--auto` or `--open-pr` across this edge.

The focused test command reports 81 passes.
The passing tests do not cover the corrective route.

The HEAD probes produced these results:

```text
press-route(in_contract_red, 0)
-> {"action": "continue", "reason": "press-corrective-cook"}

phase-decision(press, status=ok, next=press)
-> {"action": "spawn", "next_phase": "age"}

write-handoff-artifact --phase press --next press
-> exit 3: transition press -> press is not declared

parse_handoff_slug(documented Press continuation)
-> orientation == "action: continue"
```

## Findings by severity

### Blocker

- **The corrective route cannot reach Cook.** Press produces `Continue`, but the durable handoff cannot represent it. Cook then sends the result to Age. **Fix:** Add one typed local continuation to the shared handoff. Include the reason, cycle count, attack reference, and telemetry reference. Update `phase-decision` to resume corrective Cook. Keep Press-to-Cook outside the global phase registry.
- **Cook sends flags that Press does not accept.** Cook sends `--auto` and `--open-pr`. Press cannot preserve them. Cook also grants publication permission without user input. **Fix:** Define all Press inputs and flag forwarding. Forward `--open-pr` only when the user supplied it. Forward `--auto` and `--hard` through Age.

### High

- **The typed payload stops at its declaration.** Both phase files name `CurdResult`, but Press never resolves or validates that result. **Fix:** Define one durable pointer for the consumed Cook result. Require Press to validate it before the attack. Keep attempt evidence in the Press report body.
- **The tests miss the failing seam.** Current tests validate each half and lock the unconditional Age route. **Fix:** Add one producer-to-consumer test for an in-contract RED. Assert corrective Cook, the stable attack, preserved fields, and preserved flags.

### Medium

- **Press drops Cook's durable metadata.** Press omits `durable_flags` and does not define `taste_test` handling. **Fix:** Preserve `durable_flags` across Press. State that Press reads or ignores `taste_test`.
- **Press names the retired no-chain owner.** Cook now owns the fan pathway. **Fix:** Make Press honor the directive itself. Remove the Ultracook condition.

### Low

none

## STE100 Status

not compliant

- `skills/cook/SKILL.md:63` combines validation and output inspection.
- `skills/cook/SKILL.md:241-250` uses passive voice and compound instructions.
- `skills/press/SKILL.md:166` uses an unapproved metaphor.
- `skills/press/references/gap-analysis.md:55` uses three undefined abbreviations.
- This note is compliant.

## Follow-ups

- Define the typed Press continuation across shared handoff and Cook phase decision.
- Define Press auto flags and preserve only user-authorized publication intent.
- Align the `CurdResult` payload with the durable artifact contract.
- Add a complete corrective Cook seam test.
