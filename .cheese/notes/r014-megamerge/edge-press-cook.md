# Press to Cook Edge Review

## State

broken

Press produces a corrective continuation, but Cook cannot consume it.
The canonical handoff also rejects Press's documented continuation.

## Evidence

### Calls, imports, commands, and emitted files

- Press has no direct Python import from Cook.
- The Press manifest imports only shared command helpers (`src/easy_cheese/skills/press/commands.py:7-20`).
- Press exposes only `press-route` and `press-telemetry` (`src/easy_cheese/skills/press/commands.py:9-20`).
- Press links the Cook quality-gate contract (`skills/press/SKILL.md:86-92`).
- That contract calls `python3 skills/cook/scripts/cook.pyz baseline` (`skills/cook/references/quality-gates.md:5-17`).
- Cook exposes `baseline`, `phase-decision`, and the shared handoff commands (`src/easy_cheese/skills/cook/commands.py:28-39,140-151`).
- Press emits four attempt files and `.cheese/press/<slug>.md` (`skills/press/SKILL.md:44-51,94-101`).
- Press defines the report fields at `skills/press/SKILL.md:114-143`.

### Corrective continuation contract

Press accepts `press(spec_ref)` and returns one of three action types (`skills/press/SKILL.md:9-16`).
Cook accepts `cook(spec_ref, correction = false)` (`skills/cook/SKILL.md:18-28`).
Cook reserves `correction = true` for the active Press loop.
No Cook source or test accepts this parameter.
The checked scopes are `src/easy_cheese/skills/cook/**` and `tests/**`.

The route request requires exactly `outcome` and `repair_cycles` (`src/easy_cheese/shared/fanout/press_route_cli.py:12-35`).
`outcome` is a closed string enum (`src/easy_cheese/shared/fanout/press_route.py:10-16,50-62`).
`repair_cycles` is a non-Boolean integer from zero through two (`src/easy_cheese/shared/fanout/press_route.py:43-47,65-84`).
The request has no field defaults.
Missing, extra, or invalid values return a command error (`tests/fanout/python/test_press_route.py:54-76,109-155`).

| Item | Press producer | Cook consumer | State |
| --- | --- | --- | --- |
| `spec_ref` | Required Press input | Required Cook input, but absent from the continuation | broken |
| `action` | `continue`, `dispatch`, or `stop` | No Cook input accepts it | broken |
| `reason` | Defaults to `press-corrective-cook` | No Cook input accepts it | broken |
| `correction` | Not emitted | Boolean that defaults to `false` | broken |
| `repair_cycles` | Required integer in the route request | No Cook input accepts it | broken |
| attack evidence | Stable test and digest | No Cook input accepts either value | broken |
| `telemetry` | Required report path | No Cook input accepts it | broken |
| `status` and `next` | Continuation maps to `ok` and `press` | Cook routes every successful Press result to Age | broken |
| `artifact` | Press calls it an evidence path | Cook has no corrective artifact contract | broken |
| flags | Press forwards only `--hard` to Age | Cook defines `--auto`, `--hard`, and `--open-pr` | broken |

Press creates `Continue` for repair cycles zero and one (`src/easy_cheese/shared/fanout/press_route.py:74-84`).
The CLI emits `action: continue` and `reason: press-corrective-cook` (`src/easy_cheese/shared/fanout/press_route_cli.py:15-35`).
Press maps this action to `status: ok` and `next: press` (`skills/press/SKILL.md:130-143`).

The canonical parser accepts only `taste_test`, `durable_flags`, and `baseline` (`src/easy_cheese/shared/handoff.py:83-160`).
It reads `action: continue` as the orientation.
The writer rejects `press -> press` (`src/easy_cheese/shared/write_handoff_artifact.py:125-165`).
The Press phase declares only `press -> age` (`skills/press/phase-contract.yaml:5-10`).

Cook's phase table places Age after Press (`src/easy_cheese/shared/fanout/phase_decision.py:100-116,126-145`).
The table ignores `next: press` for a successful Press result.
Therefore, it starts Age instead of corrective Cook.

### Baseline contract

Cook defines `FailureRecord` with `suite`, `test_id`, and `signature` strings (`src/easy_cheese/shared/fanout/baseline.py:18-25,38-48`).
Cook identifies a test by `suite` and `test_id` (`src/easy_cheese/shared/fanout/baseline.py:58-88`).
Press says to compare only the test and signature (`skills/press/SKILL.md:88-90`).

The classifier accepts `baseline` and `current` lists.
It defaults each missing list to an empty list (`src/easy_cheese/shared/fanout/baseline.py:91-121`).
It rejects a non-list, a non-object item, or a missing required key.
Press does not define these defaults or error modes.
Press also lacks a local `baseline` command.

Cook defines a multi-line YAML baseline block (`skills/cook/references/quality-gates.md:32-46`).
Press says it reads and preserves that block (`skills/press/SKILL.md:86-101,116-128`).
The handoff model stores `baseline` as one optional string (`src/easy_cheese/shared/handoff.py:38-70`).
The renderer requires each baseline value to fit on one physical line (`src/easy_cheese/shared/handoff.py:164-184`).
No encoding or artifact reference defines the multi-line transport.

### HEAD probes

```text
press-route(in_contract_red, 0)
-> {"action": "continue", "reason": "press-corrective-cook"}

write-handoff-artifact --phase press --next press
-> exit 3: transition press -> press is not declared

parse_handoff_slug(documented Press continuation)
-> orientation == "action: continue"

phase-decision(press, status=ok, next=press)
-> {"action": "spawn", "next_phase": "age"}

render_handoff_slug(baseline=<multi-line Cook block>)
-> StatusError: baseline must fit on one physical line
```

### Tests

The focused command reports 120 passes.
Press route tests cover action selection and request errors (`tests/fanout/python/test_press_route.py:19-155`).
Cook phase tests require every successful Press result to start Age (`tests/fanout/python/test_phase_decision.py:24-36`).
The round-trip test covers only Cook to Press to Age (`tests/shared/python/test_handoff_roundtrip_integration.py:268-326`).
The handoff tests use only `baseline: none` (`tests/shared/python/test_write_handoff_artifact.py:283-345`).
The baseline document tests check prose markers only (`tests/python/test_baseline_consumer_docs.py:87-105`; `tests/python/test_cook_baseline_docs.py:95-99`).
The only continuation test checks phrase presence (`tests/python/test_wheypoint_skill_contract.py:173-186`).
No test joins the Press continuation to corrective Cook.
No test transports an actual Cook baseline block into Press.

### Contract changes

Press added `Continue`, `repair_cycles`, `action:`, and `telemetry:`.
Cook kept a prose-only `correction` Boolean and an unconditional Press-to-Age table.
Cook did not add a consumer for the new Press fields.

Cook defines a multi-line baseline block.
The canonical handoff still permits only one-line baseline values.
Press follows the logical policy, but it cannot receive the declared block.

## Findings by severity

### Blocker

- **The corrective continuation cannot reach Cook.** Press emits a local action, but the writer rejects it. The parser loses its fields. Cook then starts Age. **Fix:** Add one typed local continuation to the shared handoff model. Carry the specification reference, correction flag, cycle count, attack reference, and telemetry reference. Route this action to Cook without a global `press -> cook` transition.

### High

- **The baseline block cannot cross the handoff.** Cook defines a multi-line mapping, but the handoff permits one line. Press also lacks the classifier in its bundle. **Fix:** Store the baseline as a typed artifact or a canonical one-line reference. Expose the shared classifier through the Press bundle. Validate all `FailureRecord` string values.
- **Press cannot preserve Cook control state across a correction.** Press omits `--auto`, `--open-pr`, and `durable_flags`. It passes `--hard` only to Age. **Fix:** Define the Press input flags. Carry the original flags through corrective Cook. Forward `--open-pr` only when the user supplied it.
- **Tests do not exercise the failing seam.** Producer tests and consumer tests pass separately. Consumer tests enforce the incorrect Age route. **Fix:** Add one producer-to-consumer correction test. Assert the action, reason, fields, baseline, flags, and stable attack reference.

### Medium

none

### Low

none

## STE100 status

not compliant

- `skills/press/SKILL.md:166` uses an unapproved metaphor.
- `skills/cook/SKILL.md:63` puts two instructions in one sentence.
- `skills/press/references/gap-analysis.md:55` uses undefined abbreviations.
- `skills/cook/references/quality-gates.md:29` uses the passive voice.
- This note is compliant.

## Follow-ups

- Define the typed Press continuation and its Cook consumer.
- Define one transport for the complete baseline block.
- Add the baseline classifier to the Press bundle.
- Preserve authorized flags and durable metadata across correction.
- Add a complete Press-to-Cook seam test.
