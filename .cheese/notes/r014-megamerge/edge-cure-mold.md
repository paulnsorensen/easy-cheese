# Cure to Mold edge review

## State

broken

Cure and Mold agree on the `CurdPlan` type and the indirect phase route through Cook.
Three contract defects and one test gap prevent approval.

## Evidence

### Calls and imports

- Cure imports only shared command helpers and calls only shared bundle commands (`src/easy_cheese/skills/cure/commands.py:7-96`).
- Mold imports shared helpers and Mold modules. It does not import Cure (`src/easy_cheese/skills/mold/commands.py:7-98`).
- The two command inventories contain no cross-skill command (`src/easy_cheese/skills/cure/commands.py:10-90`; `src/easy_cheese/skills/mold/commands.py:10-93`).

### Files and handoffs

- Mold prose requires the approved spec, `PlannerResult`, `CurdPlan`, ADRs, glossary, and domain model (`skills/mold/SKILL.md:21-24`).
- Cure reads the typed plan and the domain model (`skills/cure/SKILL.md:49-53,91-94`).
- Cure does not read the Mold glossary, spec, or ADRs (`skills/cure/SKILL.md:47-100`).
- Mold sends `CurdPlan` to Cook (`skills/mold/phase-contract.yaml:5-10`).
- Cure accepts `CurdPlan` and sends `CurdResult` to Age (`skills/cure/phase-contract.yaml:5-10`).
- The registry rejects a direct Mold-to-Cure handoff (`tests/schemas/python/test_phase_contracts.py:512-532,559-575`).
- Cure emits no file, handoff field, or command to Mold (`skills/cure/phase-contract.yaml:5-10`; `src/easy_cheese/skills/cure/commands.py:66-96`).

### Types, defaults, and errors

- `CurdPlan` requires version, plan ID, revision, digest, objective, and curds (`src/easy_cheese_schemas/contracts.py:906-918`).
- Its `context` and `parent_plan_ref` fields default to `None` (`src/easy_cheese_schemas/contracts.py:919-926`).
- `PlannerResult` requires version, request ID, and disposition (`src/easy_cheese_schemas/contracts.py:1199-1209`).
- Its `plan` and `reason` fields are optional. Its `unresolved_work` field defaults to an empty tuple (`src/easy_cheese_schemas/contracts.py:1210-1218`).
- Cure stops when the plan or digest is absent or invalid (`skills/cure/SKILL.md:49-53`).
- `validate_curd_plan` rejects a wrong type or unsupported version (`src/easy_cheese_schemas/schema_runtime.py:644-667`).

### Canonical terms

- Mold writes canonical terms through `domain_model_target()` (`skills/mold/references/curdle.md:313-333`).
- Cure resolves the same target and forbids canonical term reversals (`skills/cure/references/domain-model-correction.md:5-31`).
- The resolver can return one file, one split directory, or one Hallouminate corpus (`src/easy_cheese/shared/paths.py:497-510,555-602`).
- Mold defines `Term`, optional `Avoid`, and `Code` fields (`skills/mold/references/curdle.md:321-327`).
- Cure defines the same fields, but it always shows the `Avoid` field (`skills/cure/references/domain-model-correction.md:16-24`).

## Findings

### Blocker

none

### High

- **[spec:high] Cure requires an untransported `PlannerResult`.** Mold transports only `CurdPlan`, and Cure declares only that input. Cure prose still requires the envelope. No handoff field points to it. **Fix:** Make Cure consume the validated `CurdPlan` directly. Remove the `PlannerResult` read and extraction steps.
- **[correctness:high] Cure cannot consume every domain model shape that Mold emits.** Mold permits a Hallouminate corpus and a split context directory. Cure gives no backend read protocol or context-page selection rule. **Fix:** Define read, selection, write, and read-back steps for each backend. Select the bounded-context page before any update.
- **[assertions:high] Tests do not exercise canonical-term preservation from both sides.** Resolver tests cover locations only. Mold gate tests cover write intent only. No Cure test reads and preserves a Mold entry. **Fix:** Add seam tests for one file, one split directory, and one Hallouminate adapter. Include a prohibited reversal case.

### Medium

- **[spec:medium] The `Avoid` field has two cardinality rules.** Mold omits the field when no synonym exists. Cure always shows it. **Fix:** Make Cure preserve Mold's optional field rule. Never create a placeholder synonym.

### Low

none

## Contract changes

- Mold now publishes the typed `CurdPlan` contract (`.cheese/notes/r014-megamerge/mold.md:34-39`).
- Cure did not complete this cutover because its prose still requires `PlannerResult` (`skills/cure/SKILL.md:49-53`).
- Mold supports split domain model storage. Cure does not define how to select one context page.
- No other unilateral contract change is proven at HEAD.

## Test result

- The focused command reports 186 passed and 1 skipped.
- The command covers phase contracts, path resolution, glossary consumers, and the Mold gate graph.
- The command does not cover canonical-term preservation by Cure.

## STE100 status

noncompliant

- This note complies with ASD-STE100.
- `skills/cure/SKILL.md:45,116,205,221,236,246` has passive voice, incorrect capitalization, or inconsistent terms.
- `skills/mold/SKILL.md:3,12,19,24,131` joins instructions or exceeds the sentence limit.
- `skills/mold/references/curdle.md:300,315,329-333` uses long descriptive sentences and passive voice.
- `skills/cure/references/domain-model-correction.md:1-32` complies with ASD-STE100.

## Follow-ups

- Make Cure consume the canonical `CurdPlan` input.
- Define Cure behavior for Hallouminate and split domain model stores.
- Align the optional `Avoid` field rule.
- Add producer-to-consumer canonical-term tests.
