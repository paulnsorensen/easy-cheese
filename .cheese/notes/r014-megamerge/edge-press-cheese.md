# Press to Cheese edge review

## State

broken

Press emits a corrective action that Cheese cannot parse from the documented Press report.

## Evidence

### Calls, imports, commands, and files

- Press has no direct Python import from Cheese.
- Press links the Cheese code intelligence contract at `skills/press/SKILL.md:103`.
- Press links the Cheese portability contract at `skills/press/SKILL.md:105-106`.
- Press links the Cheese handback contract at `skills/press/SKILL.md:128`.
- Press links the Cheese handoff gate at `skills/press/SKILL.md:145-151`.
- The Press command manifest imports only shared command helpers (`src/easy_cheese/skills/press/commands.py:7-24`).
- `press-route` accepts only `outcome` and `repair_cycles` (`src/easy_cheese/shared/fanout/press_route_cli.py:12-35`).
- `outcome` accepts four string values (`src/easy_cheese/shared/fanout/press_route.py:10-16,50-62`).
- `repair_cycles` accepts non-Boolean integers from zero through two (`src/easy_cheese/shared/fanout/press_route.py:43-47,65-71`).
- Missing, extra, or invalid values return an error (`tests/fanout/python/test_press_route.py:54-76,109-129`).
- A RED route returns `action: continue` and `reason: press-corrective-cook` (`press_route.py:19-24,74-84`; `press_route_cli.py:15-22`).
- A GREEN route returns `action: dispatch` and `command: /age` (`press_route.py:26-30,79-80`).
- A stop returns `reason` and `gated_evidence` (`press_route.py:33-38,84-87`).
- `press-telemetry` emits a Press attempt record, not a Cheese input (`skills/press/SKILL.md:55-72`).
- Press emits candidate, route, telemetry request, and telemetry record files (`skills/press/SKILL.md:44-51`).
- Press emits `.cheese/press/<slug>.md` for the durable handoff (`skills/press/SKILL.md:94-101,114-128`).
- Cheese resolves that report through Wheypoint (`skills/cheese/SKILL.md:107-117`).
- Cheese does not consume the four attempt files (`skills/cheese/references/continue-resume.md:14-32,67-70`).
- The code intelligence link and its backend rules agree (`skills/cheese/references/code-intelligence-routing.md:3-24`).
- The Press command paths follow the portability rule (`skills/cheese/references/harness-portability.md:7-19`).

### Handoff fields

| Field | Press producer | Cheese consumer | State |
| --- | --- | --- | --- |
| `status` | Canonical status is required. | Canonical status is required. | ok |
| `next` | `age`, `press`, or `done` is required. | A runnable global phase or `done` is required. | broken |
| `artifact` | An evidence path is required. | The prior consumed report is required. | broken |
| `baseline` | The Cook baseline is optional. | The parser accepts the optional field. | ok |
| `action` | The field is required. | The parser does not support the field. | broken |
| `telemetry` | The record path is required. | The parser does not support the field. | broken |
| orientation | The line follows `action` and `telemetry`. | The first unknown line becomes the orientation. | broken |
| `continue` | Press does not emit this field. | Cheese expects `press-corrective-cook`. | broken |

Press maps a corrective action to `next: press` and `action: continue` (`skills/press/SKILL.md:130-136`).
Cheese maps `next: press` to a new `/press <slug>` dispatch (`skills/cheese/references/continue-resume.md:109-120`).
Cheese instead names `continue: press-corrective-cook` for the local action (`skills/cheese/SKILL.md:120-122`).

The canonical parser accepts only three optional keys (`src/easy_cheese/shared/handoff.py:83-160`).
It treats `action:` as orientation and ignores the later Press lines.
The HEAD parser probe confirmed this result.

The canonical writer validates each phase transition (`src/easy_cheese/shared/write_handoff_artifact.py:125-173`).
The Press phase declares only the Age destination (`skills/press/phase-contract.yaml:5-10`).
The HEAD writer probe rejected `press -> press` with exit code 3.

Press defines `artifact:` as an evidence path (`skills/press/SKILL.md:116-125`).
The handback contract defines it as the prior report (`skills/cheese/references/handback-contract.md:15-32`).
Cheese forwards the value unchanged (`skills/cheese/SKILL.md:120-122`).

### Tests

- The focused seam suite reports 68 passes.
- Press route tests cover the action union and input errors (`tests/fanout/python/test_press_route.py:19-76,79-129`).
- Round-trip tests cover Cook to Press and Press to Age (`tests/shared/python/test_handoff_roundtrip_integration.py:216-326`).
- The Press to Age test uses the canonical four-field preamble.
- The Cheese test checks phrase presence only (`tests/python/test_wheypoint_skill_contract.py:173-186`).
- No test joins an actual corrective Press report to the Cheese parser.

### Contract changes

Press added `Continue`, `action:`, and `telemetry:` (`skills/press/SKILL.md:9-16,114-137`).
Cheese added the different `continue:` name (`skills/cheese/SKILL.md:120-122`).
The canonical handoff grammar added neither action field (`skills/cheese/references/handback-contract.md:15-32`).
The Press phase registry added no local continuation (`skills/press/phase-contract.yaml:5-10`).

## Findings by severity

### Blocker

- **Cheese cannot resume Press's corrective Cook action.** The writer rejects `next: press`. The parser also misreads the Press fields. Cheese can start a new Press phase instead. **Fix:** Add one typed local action to the canonical handoff model. Render and parse it through shared code. Keep `next:` for global phases.

### High

- **Press and Cheese assign different meanings to `artifact:`.** Press can send attack evidence where Cheese expects the Cook report. **Fix:** Put the consumed Cook report in `artifact:`. Put attempt paths in the report body.
- **Tests do not protect the corrective continuation seam.** Current tests validate each half without joining them. **Fix:** Add one producer-to-consumer test for a RED result. Assert the action, reason, artifact, flags, and no global Press dispatch.

### Medium

none

### Low

none

## STE100 status

not compliant

- `skills/press/SKILL.md:166` uses an unapproved metaphor. Delete it.
- `skills/press/references/gap-analysis.md:55` uses undefined abbreviations. Use `attempt 1`, `attempt 2`, and `attempt 3`.
- `skills/cheese/SKILL.md:42` combines classification and fallback instructions. Split the steps.
- `skills/cheese/SKILL.md:136` has a procedural sentence longer than 20 words. Split it.
- `skills/cheese/references/code-intelligence-routing.md:23` has a procedural sentence longer than 20 words. Split it.
- `skills/cheese/references/handback-contract.md:74-77` has a descriptive sentence longer than 25 words. Split it.
- `skills/cheese/references/handoff-gate.md:141` has a procedural sentence longer than 20 words. Split it.
- `skills/cheese/references/harness-portability.md:19` has a procedural sentence longer than 20 words. Split it.
- This note is compliant.

## Follow-ups

- Define one typed Press continuation in the canonical handoff contract.
- Update the writer, parser, Press report, and Cheese resume logic.
- Correct the Press `artifact:` definition.
- Add the producer-to-consumer continuation test.
