# Mold to Cook edge review

## State

broken

## Evidence

### Mold producer

- `skills/mold/phase-contract.yaml:5-10` declares `mold -> cook` with `curd-plan`.
- `src/easy_cheese/skills/mold/contract_handlers.py:33-85` publishes this route.
- The command requires a document, invocation file, operation ID, and artifact root.
- The command writes canonical `HandoffPointer` JSON to stdout.
- `src/easy_cheese/shared/publication.py:504-514,556-629` stores the pointer under `pointers/<operation-id>.json`.
- `src/easy_cheese/shared/taste_test.py:1142-1186` instead builds `/cook --auto <spec_ref>`.
- `skills/mold/SKILL.md:21-24,109,127-133` uses the same specification path route.
- A full search of `skills/mold/**` found no instruction that calls `mold.pyz publish`.

### Cook consumer

- `skills/cook/phase-contract.yaml:5-14` accepts `curd-plan` from Mold.
- `skills/cook/SKILL.md:30-36` tells Cook to call `accept` for a Mold handoff pointer.
- `src/easy_cheese/skills/cook/contract_handlers.py:119-143` fixes the destination to `cook`.
- The same handler fixes the payload schema to `curd-plan`.
- The handler accepts a pointer file path and emits a canonical plan wrapper.
- `src/easy_cheese/shared/publication.py:453-490,693-735` validates the route, payload, receipt, and schema.

### Shared types and defaults

- `src/easy_cheese_schemas/contracts.py:678-692` defines the common `HandoffPointer`.
- Its route, operation, digest, and payload fields are required.
- Its `normalization_receipt` field defaults to `null`.
- `src/easy_cheese_schemas/contracts.py:906-977` defines the common `CurdPlan`.
- Its `context` and `parent_plan_ref` fields default to `null`.
- `src/easy_cheese_schemas/contracts.py:1199-1228` defines `PlannerResult`.
- Mold persists this result, but the phase handoff carries its `CurdPlan`.
- Cook accepts either typed value as semantic authority at `skills/cook/SKILL.md:74-85`.

### Error modes and tests

- Mold returns status 1 for read, JSON, schema, route, or publication failures.
- Cook returns status 1 for schema, route, or publication failures.
- Argparse uses status 2 for invalid command arguments on both sides.
- `tests/python/test_mold_contract_publish.py:85-151` tests the producer command.
- `tests/python/test_cook_contract_accept.py:116-235` tests both commands together.
- `tests/python/test_curd_count.py:329-377` locks the old specification path handoff.
- `tests/python/test_mold_taste_test.py:659-675` locks the same path and metadata envelope.
- The focused bundle run reported 11 passes and four failures.
- The route tests reported 51 passes.

## Findings by severity

### Blocker

- **The normal handoff bypasses canonical acceptance.** Mold sends a specification path instead of the stored `HandoffPointer` path. Cook runs `accept` only for a handoff pointer. The normal route therefore skips route, receipt, and immutable artifact checks. The producer stdout type also differs from the consumer path input. Current route tests require this bypass. **Fix:** Run Mold `publish` after approval. Persist and pass its pointer path. Make Cook run `accept` before any executor. Verify the accepted plan digest against the approved plan. Add one test from Curdle output through Cook acceptance.

### High

- **Cook can fetch HTTPS from a tampered pointer.** Publication calls the shared resolver at `src/easy_cheese/shared/publication.py:428-450`. The resolver permits HTTPS at `src/easy_cheese_schemas/artifacts.py:65-113`. It opens that URL at `src/easy_cheese_schemas/artifacts.py:346-405`. The local-only assertion fails at `tests/python/test_cook_contract_accept.py:226-235`. **Fix:** Add an allowed scheme policy to `resolve_artifact`. Set publication acceptance to `file` only. Keep the artifact root restriction.
- **Cook tests use stale resolver errors.** Three assertions expect old digest and missing-file messages at `tests/python/test_cook_contract_accept.py:136-168,215-223`. The resolver now reports size mismatch before digest mismatch. It reports unreadable artifacts for missing files. **Fix:** Define stable Cook error categories. Update the three assertions to use those categories.

### Medium

none

### Low

none

## STE100 status

- `skills/mold/SKILL.md:12-13,21-24,131` still needs work. These lines combine instructions and exceed the procedural sentence limit.

The reviewed Cook prose and this note are compliant.

## Follow-ups

- Wire the published `HandoffPointer` path into the normal Mold to Cook route.
- Restrict publication acceptance to local artifact URIs.
- Define stable Cook error categories and update the failing assertions.
- Split the long Mold flow sentences into single instructions.
