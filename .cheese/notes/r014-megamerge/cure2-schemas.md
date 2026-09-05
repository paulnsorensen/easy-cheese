# Schemas cure round 2

This node applies the review, edge, and hub findings for the `schemas` area.
It edits only files in the `schemas` area paths.
It records each fix that belongs to another area as `deferred`.

## Finding table

| Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-schemas.md | high | Legacy receipts permit two source identities. | applied | `6a71e452` | `src/easy_cheese_schemas/contracts.py:676-690` |
| review-schemas.md | high | The published receipt schema accepts null legacy source values. | applied | `6a71e452` | `src/easy_cheese_schemas/contracts.py:145-166`; `tests/schemas/python/goldens/normalization-receipt.json:1` |
| review-schemas.md | medium | Mini-spec normalization records probes that did not occur. | deferred: owned by mold | none | `src/easy_cheese/skills/mold/validate_spec.py:617-632` |
| review-schemas.md | low | Guard rules use tracer-only names and descriptions. | deferred: owned by mold and shared | none | The rename regenerates `src/easy_cheese/shared/document_rules.py:9,45` and `skills/mold/references/curdle.md:175,187`. |
| review-schemas.md | low | Comments and tests retain retired source paths. | applied | `ce662297` | `src/easy_cheese_schemas/compat.py:9-11`; `tests/python/fixtures/spec_format/valid_spec.md:72` |
| review-schemas.md | simplification | The receipt stores the source schema URI twice. | applied as equality | `6a71e452` | The compatibility contract keeps both published fields. The model now requires them to agree at `src/easy_cheese_schemas/contracts.py:685-690`. |
| review-schemas.md | simplification | Rename `tracer-row-blank-matrix-cells`. | deferred: owned by mold and shared | none | The rename touches the same generated files as the low finding above. |
| edge-build-schemas.md | high | The writer reference omits the kind-to-payload map and the defaults. | deferred: owned by build | none | `scripts/render_generated_regions.py:151-165` |
| edge-build-schemas.md | high | The normal test command skips the bundle seam. | deferred: owned by build | none | `justfile:2,15-31` |
| edge-build-schemas.md | medium | `_ContractVersion` declares string values as integers. | deferred: owned by build | none | `scripts/render_generated_regions.py:53-56` |
| edge-build-schemas.md | medium | The build offers no command that writes the generated runtime files. | deferred: owned by build | none | `scripts/build_pyz.py:112-154` |
| edge-build-schemas.md | low | Cook prose names the wrong schema generator. | deferred: owned by cook | none | `skills/cook/SKILL.md:123` |
| edge-build-schemas.md | ste100 | The Curdle reference holds an incomplete sentence. | deferred: owned by mold | none | `skills/mold/references/curdle.md:158` |
| edge-schemas-build.md | medium | The build declares phase version numbers as integers. | deferred: owned by build | none | This row repeats the `_ContractVersion` finding above. |
| edge-schemas-build.md | medium | The generated writer reference hides optional fields and defaults. | deferred: owned by build | none | This row repeats the writer reference finding above. |
| edge-schemas-mold.md | high | The strict mini-spec path invents canonical evidence. | deferred: owned by mold and shared | none | `src/easy_cheese/skills/mold/validate_spec.py:595-634`; `src/easy_cheese/shared/taste_test.py:662-689` |
| edge-schemas-mold.md | medium | Tests do not run the documented mini-spec against the contract. | deferred: owned by mold | none | `tests/python/test_mold_taste_test.py:207-216` |
| edge-schemas-mold.md | ste100 | Mold prose uses the passive voice and a noun list. | deferred: owned by mold | none | `skills/mold/SKILL.md:94-100`; `skills/mold/references/mini-spec-mode.md:31` |
| edge-schemas-shared.md | blocker | Normalization changes valid payload text. | applied by shared | `b18b463b` | That fix broke one shared test. See `Follow-ups`. |
| edge-schemas-shared.md | blocker | Replay ignores the operation identity. | applied by shared | `466ce044` | `src/easy_cheese/shared/publication.py:517-526` |
| edge-schemas-shared.md | high | Legacy source identities can disagree. | applied | `6a71e452` | `src/easy_cheese_schemas/contracts.py:685-690` |
| edge-schemas-shared.md | high | The emitted receipt schema accepts null legacy source values. | applied | `6a71e452` | `tests/schemas/python/test_contracts.py:1124-1185` |
| edge-schemas-shared.md | high | Shared reads an unbounded pointer before schema validation. | deferred: owned by shared | none | `src/easy_cheese/shared/publication.py:418-425` |
| edge-schemas-shared.md | high | Shared invents missing Grounding probes. | deferred: owned by shared | none | `src/easy_cheese/shared/taste_test.py:681-689` |
| edge-schemas-wheypoint.md | blocker | Lineage accepts an impossible root. | applied | `3de3c695` | The model rejects a later revision without a parent at `src/easy_cheese_schemas/wheypoint.py:690-700`. |
| edge-schemas-wheypoint.md | blocker | The walker compares no work identifier and no revision number. | deferred: owned by wheypoint | none | `src/easy_cheese/skills/wheypoint/lineage.py:68-124` |
| edge-schemas-wheypoint.md | high | Lint accepts an incomplete compaction proof. | deferred: owned by wheypoint | none | `src/easy_cheese/skills/wheypoint/lint.py:399-452` |
| edge-schemas-wheypoint.md | high | Lint accepts a prior compaction that points forward or to itself. | deferred: owned by wheypoint | none | `src/easy_cheese/skills/wheypoint/lint.py:415-451` |
| edge-schemas-wheypoint.md | high | Wheypoint prose omits the schema value `cut`. | deferred: owned by wheypoint | none | `skills/wheypoint/SKILL.md:79-82` |
| edge-shared-schemas.md | high | Malformed legacy input escapes the command error contract. | applied | `fb61b3bc` | `src/easy_cheese_schemas/compat.py:444-508`; `tests/python/test_schemas_compat.py:342-410` |
| edge-shared-schemas.md | high | A legacy receipt can contain two source identities. | applied | `6a71e452` | This row repeats the receipt identity finding above. |
| edge-shared-schemas.md | high | The generated schema permits null legacy source values. | applied | `6a71e452` | This row repeats the null source finding above. |
| hub-schemas.md | blocker | Age can leave a malformed report before transition validation. | deferred: owned by age | none | `skills/age/SKILL.md:112-115` |
| hub-schemas.md | blocker | Cook ignores valid plan dependencies during execution. | deferred: owned by cook | none | `src/easy_cheese/skills/cook/workflow.py:1252-1277` |
| hub-schemas.md | blocker | Cure cannot apply a selected subset through its typed API. | deferred: owned by cure | none | `src/easy_cheese/skills/cook/workflow.py:1192-1210` |
| hub-schemas.md | high | Age removes required upstream handback state. | deferred: owned by age | none | `tests/python/test_age_review_lock.py:38-47` |
| hub-schemas.md | high | Cheese does not consume the full phase registry. | deferred: owned by cheese | none | `skills/cheese/references/continue-resume.md:98-122` |
| hub-schemas.md | medium | Cook bypasses the schema error path for invalid UTF-8. | deferred: owned by cook | none | `src/easy_cheese/skills/cook/contract_handlers.py:53-64` |
| hub-schemas.md | medium | Cure has no successful direct seam test. | deferred: owned by cure | none | `tests/schemas/python/test_workflow_thread.py:766-919` |
| hub-schemas.md | medium | Mold records probes that did not occur. | deferred: owned by mold | none | This row repeats the mini-spec Grounding finding above. |

## Applied commits

- `6a71e452` fix(schemas): enforce one legacy source identity in normalization receipts.
- `fb61b3bc` fix(schemas): reject malformed legacy curd-plan input in the adapter.
- `3de3c695` fix(schemas): reject a later wheypoint revision that names no parent.
- `ce662297` docs(schemas): name current package paths in comments and fixtures.
- `ef693041` refactor(schemas): keep the new legacy guards free of unknown types.
- `9f9677f7` test(typing): silence unused-result warnings in gateway and storage tests.
  This commit touches two files outside the area. The repo-wide typecheck gate refused the node without it.
  See `Disagreements` for the reason.

## Regression tests

- `tests/schemas/python/test_contracts.py` rejects a receipt with two source identities at the model seam and at the gateway seam.
- `tests/schemas/python/test_contracts.py` reads the emitted conditional and rejects each null legacy source value.
- `tests/python/test_schemas_compat.py` rejects five malformed 0.9 payloads and accepts the well-formed payload.
- `tests/schemas/python/test_wheypoint_conformance.py` rejects revision two without a parent.

## Disagreements

- `review-schemas.md` offers two fixes for the duplicate source URI. It permits equality validation or field removal.
  I chose equality validation. The published schema and the shared gateway both read both fields today.
  Rule 3 keeps the typed schema contract, so the model now requires the two values to agree.
- `edge-schemas-wheypoint.md` asks for four lineage rules. Two rules belong to the model and two rules belong to the walker.
  I applied the model rule that a null parent means revision one. I did not add the reverse rule.
  The reverse rule refuses revision one with a parent. That rule breaks three wheypoint tests that build such receipts on purpose.
  The edge note does not ask for the reverse rule.

- The reconcile gate runs `just typecheck` across the whole repository.
  Commits `b18b463b` and `61fadbf7` left five unused-result warnings in `shared` and `wheypoint` test files.
  The scope rule keeps fixes inside the area. The gate rule refuses the node while any warning remains.
  I chose the gate rule, because the same five warnings block every later node on this branch.
  Commit `9f9677f7` assigns each discarded call result to `_`. It changes no test behaviour.
  I did not repair the two failing tests in those areas. Those repairs change test intent, so they stay deferred.

## Verification

- `uvx ruff check .` passes.
- `just typecheck` reports zero errors and zero warnings after commit `9f9677f7`.
- `scripts/render_generated_regions.py --check` passes.
- The area suites pass 785 tests and skip three tests.
- `tests/shared/python` passes 409 tests. `tests/fanout/python` passes 657 tests.

## Follow-ups

- `tests/python/test_publication_gateway.py::test_syntax_normalize_normalize_quotes_recovers` fails at HEAD.
  Commit `b18b463b` in the `shared` area caused this failure. The repair selector now refuses a curly-quoted object.
  The `shared` area owns the fix.
- `tests/wheypoint/python/test_storage.py::test_promotion_refuses_a_triple_that_does_not_agree[revision_number]` fails at HEAD.
  The test changes a genesis receipt to revision nine, which the model now refuses before storage sees it.
  The `wheypoint` area owns the fix. Give that case a parent revision, or expect `ValueError`.
- `src/easy_cheese/shared/migrate.py` must wrap `LegacyConversionError` in `UnsupportedLegacySourceError`.
  The Mold handler catches only the shared error type at `src/easy_cheese/skills/mold/contract_handlers.py:136-143`.
  The `shared` area owns this fix.
- Every other deferred row in the table above needs its named area to apply it.

## STE100 status

compliant

- The `schemas` area contains no `SKILL.md` file and no `references/` file.
- The one prose file in this area is `tests/python/fixtures/spec_format/valid_spec.md`. It complies.
- This note complies.
