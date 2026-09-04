# Cook to Mold Edge Review

## State

broken

The declared registry route matches.
The executable and prose contracts do not complete the route.

## Evidence

| Surface | Cook side | Mold side | State |
| --- | --- | --- | --- |
| Route declaration | Cook declares a `PlannerRequest` payload to Mold (`skills/cook/phase-contract.yaml:13-14`). | Mold declares the same schema as input (`skills/mold/phase-contract.yaml:6-7`). | ok |
| Trigger | Cook routes ambiguity and specification failures to Mold (`skills/cook/SKILL.md:49-54,170-175`). | Mold defines only user and Cheese entry modes (`skills/mold/SKILL.md:10-24,45-51`). | broken |
| Request ownership | Cook builds and dispatches its own planner request (`skills/cook/references/fan-pathway.md:52-67`). | Mold also builds and dispatches its own planner request (`skills/mold/SKILL.md:21-23`). | broken |
| Request fields | Cook does not map a failure to a request kind or its conditional fields (`skills/cook/SKILL.md:163-174`). | Mold does not define an intake for Cook's request (`skills/mold/SKILL.md:15-24,127-133`). | broken |
| Emitted file | Cook writes `.cheese/cook/<slug>.md` with handoff fields (`skills/cook/SKILL.md:131-165`). | Mold does not name this file or a reader for this route (`skills/mold/SKILL.md:127-133`). | broken |
| Handoff fields | The handoff contains status, reason, next, artifact, orientation, and three optional fields (`src/easy_cheese/shared/handoff.py:38-80`). | No handoff field carries the payload schema (`src/easy_cheese/shared/handoff.py:83-87,164-184`). | broken |
| Command | Cook exposes `write-handoff-artifact` and `read-handoff-slug` (`src/easy_cheese/skills/cook/commands.py:140-151,238-244`). | Mold exposes no planner-request intake or handoff reader (`src/easy_cheese/skills/mold/commands.py:10-94`). | broken |
| Validation | The writer validates route metadata, then accepts any artifact string (`src/easy_cheese/shared/write_handoff_artifact.py:125-162,243-280`). | Mold has no command that validates the referenced `PlannerRequest` (`src/easy_cheese/skills/mold/commands.py:10-94`). | broken |
| Error mode | Cook says to stop on an unanswered decision, but it also says to use Mold (`skills/cook/references/package-report.md:61-74`; `skills/cook/SKILL.md:174`). | Mold retries only its own invalid planner result before approval (`skills/mold/SKILL.md:21,119`). | broken |
| Imports | Cook imports shared and schema modules, but it imports no Mold module (`src/easy_cheese/skills/cook/commands.py:7-11,14-186`; `src/easy_cheese/skills/cook/contract_handlers.py:20-31`). | Mold imports shared and schema modules, but it imports no Cook module (`src/easy_cheese/skills/mold/commands.py:7-61`). | ok |
| Tests | Registry tests compile both declarations and assert Mold's input (`tests/schemas/python/test_phase_contracts.py:124-154`). | Direct writer tests cover only Mold to Cook (`tests/schemas/python/test_phase_contracts.py:194-209,498-556`). | untested |

`PlannerRequest` requires `contract_version`, `request_id`, `kind`, and `objective`.
It defaults `evidence` to an empty tuple and `source_plan_ref` to `None` (`src/easy_cheese_schemas/contracts.py:1034-1065`).
`decompose` forbids a source plan.
`replan` requires one.
`remediate` requires a source plan and evidence (`src/easy_cheese_schemas/contracts.py:1034-1080`).
Neither skill defines this mapping for a Cook specification failure.

The phase contract test reports 37 passed tests.
A bundle probe used `/tmp/not-a-planner-request.txt` as the artifact.
The Cook writer returned success and omitted the payload schema from the handoff.

## Findings by severity

### Blocker

- **The declared payload never crosses a validated boundary.** Cook can write an arbitrary artifact string after route validation (`src/easy_cheese/shared/write_handoff_artifact.py:125-162`). The handoff omits the schema (`src/easy_cheese/shared/handoff.py:38-47,164-184`). Mold has no intake command (`src/easy_cheese/skills/mold/commands.py:10-94`). **Fix:** Add one canonical Cook emission command. Publish a validated `PlannerRequest`. Put its typed pointer in `artifact`. Add a Mold intake command that validates the pointer, route, and payload.

### High

- **Cook and Mold assign different owners to the planner request.** Cook dispatches a request directly to `easy_cheese_schemas.plan` (`skills/cook/references/fan-pathway.md:62-67`). Mold also creates the request from its current draft (`skills/mold/SKILL.md:21`). Mold never consumes Cook's request. **Fix:** Make Mold own planning after a Cook specification failure. Make Cook emit only the validated request and failure evidence.
- **Failure semantics do not select a valid request.** Cook names a deliberate replan and a general specification failure (`skills/cook/SKILL.md:163-174`). The model requires different fields for `decompose`, `remediate`, and `replan` (`src/easy_cheese_schemas/contracts.py:1034-1080`). **Fix:** Define one request kind for each failure class. Define every required field and rejection mode.
- **The status rules can stop the Mold route.** Cook says to stop for unanswered decisions and design changes (`skills/cook/references/package-report.md:61-74`; `skills/cook/SKILL.md:219-230`). `gated` and `halt` stop, while `needs-context` retries (`src/easy_cheese_schemas/handback_status.py:54-61`). The Cook contract also excludes Mold from its result (`skills/cook/SKILL.md:18-20`). **Fix:** Define one routable status for `next: mold`. Add Mold to the Cook result contract.

### Medium

- **Tests do not exercise the complete edge.** Registry tests protect declaration compatibility (`tests/schemas/python/test_phase_contracts.py:124-154`). Writer tests exercise only Mold to Cook (`tests/schemas/python/test_phase_contracts.py:194-209,498-556`). The Cook and Mold bundle tests also cover only Mold to Cook (`tests/python/test_cook_contract_accept.py:1-5`; `tests/python/test_mold_contract_publish.py:85-105`). **Fix:** Add one Cook-to-Mold bundle test. Require payload validation, request-kind validation, status routing, and consumer rejection cases.

### Low

none

## STE100 status

not compliant

- `skills/cook/SKILL.md:63,241,250` combines instructions or uses passive voice.
- `skills/mold/SKILL.md:3,12-13,19,21,24,131,138-146` joins instructions or exceeds sentence limits.
- This review note complies with the required writing rules.

## Follow-ups

- Implement the validated Cook-to-Mold planner-request boundary.
- Define the request-kind and handoff-status rules for each specification failure.
- Add end-to-end tests from Cook emission through Mold intake.
- Correct the listed STE100 violations in both skill files.
