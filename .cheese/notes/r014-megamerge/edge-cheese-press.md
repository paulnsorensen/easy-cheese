# Cheese to Press Edge Review

## State

broken

Cheese cannot resume Press's corrective Cook continuation from the documented durable handoff.

## Evidence

### Calls, imports, commands, and files

- Cheese has no direct Python import from Press.
- The checked scope was `skills/cheese/**`.
- Cheese resumes an artifact through `/wheypoint resolve --ref` (`skills/cheese/SKILL.md:107-117`).
- Press runs `press-route` with `outcome` and `repair_cycles` (`skills/press/SKILL.md:20-42`).
- The request requires exactly those two keys (`src/easy_cheese/shared/fanout/press_route_cli.py:12-35`).
- `outcome` is a string enum (`src/easy_cheese/shared/fanout/press_route.py:10-16,50-62`).
- `repair_cycles` is a non-Boolean integer from zero through two (`src/easy_cheese/shared/fanout/press_route.py:43-47,65-71`).
- Missing, extra, or invalid command input returns an error (`tests/fanout/python/test_press_route.py:54-76,109-155`).
- A RED route returns `Continue` (`src/easy_cheese/shared/fanout/press_route.py:74-84`).
- Its `reason` defaults to `press-corrective-cook` (`src/easy_cheese/shared/fanout/press_route.py:19-24`).
- Press emits candidate, route, telemetry request, and telemetry record files (`skills/press/SKILL.md:44-51`).
- Press also emits `.cheese/press/<slug>.md` (`skills/press/SKILL.md:94-101,114-128`).
- Cheese resumes the supplied report instead of the attempt files (`skills/cheese/references/continue-resume.md:14-32,67-70`).

### Handoff fields

| Field | Press producer | Cheese consumer | State |
| --- | --- | --- | --- |
| `status` | Required canonical status | Required canonical status | ok |
| `next` | `age`, `press`, or `done` | A runnable global phase or `done` | broken |
| `artifact` | Evidence path | Prior consumed report | broken |
| `baseline` | `none` or the Cook block | Optional parsed key | ok |
| `action` | Required Press key | Unsupported key | broken |
| `telemetry` | Required Press path | Unsupported key | broken |
| orientation | After `action` and `telemetry` | First unknown line | broken |
| `continue` | Not emitted | Expected as `press-corrective-cook` | broken |

Press maps `Continue` to `next: press` and `action: continue` (`skills/press/SKILL.md:130-136`).
Cheese treats `next: press` as `/press <slug>` (`skills/cheese/references/continue-resume.md:109-120`).
Cheese instead names `continue: press-corrective-cook` as the local action (`skills/cheese/SKILL.md:120-122`).

The canonical parser accepts only three optional keys (`src/easy_cheese/shared/handoff.py:83-160`).
It does not accept `action:` or `telemetry:`.
A HEAD probe read `action: continue` as the orientation and ignored the later lines.

The writer validates each phase transition before it writes (`src/easy_cheese/shared/write_handoff_artifact.py:125-165`).
Press declares only an Age destination (`skills/press/phase-contract.yaml:5-10`).
A HEAD probe rejected `press -> press` with exit code 3.

Press calls `artifact:` an evidence path (`skills/press/SKILL.md:116-125`).
The shared contract defines it as the prior report (`skills/cheese/references/handback-contract.md:15-32`).
Cheese forwards this value unchanged (`skills/cheese/SKILL.md:120-122`).

### Tests

- Press route tests cover the action union and command errors (`tests/fanout/python/test_press_route.py:19-76,79-155`).
- Round-trip tests cover Cook to Press and Press to Age (`tests/shared/python/test_handoff_roundtrip_integration.py:136-206`).
- Writer tests cover only the global Press-to-Age route (`tests/shared/python/test_write_handoff_artifact.py:93-115,485-502`).
- The Cheese-side test checks phrase presence only (`tests/python/test_wheypoint_skill_contract.py:173-186`).
- A full `tests/**` search found no handoff fixture with `action: continue` or `telemetry:`.

The tests do not exercise the producer-to-consumer continuation seam.

### Contract change

Press added `Continue` plus the `action:` and `telemetry:` report fields (`skills/press/SKILL.md:9-16,114-137`).
Cheese added a different `continue:` name (`skills/cheese/SKILL.md:120-122`).
The canonical handoff grammar did not add either field (`skills/cheese/references/handback-contract.md:15-32`).
The phase registry did not add a local continuation action (`skills/press/phase-contract.yaml:5-10`).

## Findings by severity

### Blocker

- **Press cannot publish or resume its corrective Cook action.** The writer rejects `next: press`. The parser also misreads the required Press fields. Cheese then selects a global Press dispatch instead of corrective Cook. **Fix:** Add one typed local action to the canonical handoff model. Render and parse that action through shared code. Let Cheese select `press-corrective-cook` from the typed action. Keep `next:` for global phase transitions. Do not register `press -> press` as a global route.

### High

- **Press and Cheese assign different meanings to `artifact:`.** Press can send attack evidence where Cheese expects the consumed Cook report. **Fix:** Put the consumed Cook report in `artifact:`. Put attack, route, and telemetry paths in the Press report body.
- **Tests do not protect the corrective continuation seam.** Current tests validate each half without joining them. **Fix:** Add one producer-to-consumer test for an in-contract RED. Write and parse the report. Assert the corrective Cook action, reason, artifact, and preserved flags. Assert that Cheese does not dispatch global Press.

### Medium

none

### Low

none

## STE100 Status

- `skills/cheese/SKILL.md` is not compliant.
  Line 42 combines classification, selection, and fallback instructions.
  Split them into separate sentences.
- `skills/press/SKILL.md` is not compliant.
  Line 166 uses an unapproved metaphor.
  Delete it.
- This note is compliant.

## Follow-ups

- Define the typed Press continuation in the canonical handoff contract.
- Update the writer, parser, phase router, and Cheese resume logic.
- Correct the Press `artifact:` definition.
- Add the producer-to-consumer continuation test.
