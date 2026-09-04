# Schemas to Shared Edge Review

## State

broken

Two blocker defects and four high-severity defects break normalization, pointer, receipt, and Grounding behavior.

## Evidence

### Direct imports

- `src/easy_cheese/shared/handoff.py:25-31` and `src/easy_cheese/shared/handoff_cli.py:22-26` import the schema-owned handback status functions.
- `src/easy_cheese/shared/migrate.py:22-33` imports the exact adapter, receipt, version, digest, and validation services.
- `src/easy_cheese/shared/publication.py:31-54` imports pointer, normalization, transition, validation, and artifact services.
- `src/easy_cheese/shared/taste_test.py:20-33` imports Grounding and Mold document models.
- `src/easy_cheese/shared/document_rules.py:6-53` contains model metadata that the schema compiler emits.
- `src/easy_cheese/shared/manifest_io.py:10` imports the schema manifest parser and its error type.
- `src/easy_cheese/shared/fanout/validate_decomposition.py:8-14` imports decomposition models and the compatibility loader.
- `src/easy_cheese/shared/fanout/validate_pr_plan.py:19-27` imports the `PrPlan` model and loader.
- `src/easy_cheese/shared/fanout/wiring.py:12-17` and `src/easy_cheese/shared/fanout/wiring_topo_sort.py:16-18` import schema graph functions.
- `src/easy_cheese/shared/fanout/phase_decision.py:69-79` imports the schema-owned status vocabulary.
- No file under `src/easy_cheese_schemas` imports `easy_cheese.shared`.

### Contract trace

| Contract | Schema evidence | Shared evidence | Test evidence |
| --- | --- | --- | --- |
| Normalization | `src/easy_cheese_schemas/contracts.py:623-692` defines actions, receipts, and pointers. | `src/easy_cheese/shared/publication.py:418-490,529-735` validates, persists, emits, and accepts them. | `tests/schemas/python/test_contracts.py:1014-1077`; `tests/python/test_publication_gateway.py:96-160,337-371` |
| Legacy adapter | `src/easy_cheese_schemas/compat.py:409-425,487-550` owns the exact adapter and its sunset. | `src/easy_cheese/shared/migrate.py:62-128` performs exact lookup, conversion, validation, and publication. | `tests/python/test_schemas_compat.py:324-417`; `tests/python/test_contract_migrate.py:76-170` |
| Grounding | `src/easy_cheese_schemas/contracts.py:2338-2356,2450-2465,2487-2537,2604-2617` defines values, rows, metadata, and exact coverage. | `src/easy_cheese/shared/document_rules.py:6-53` matches the metadata. `src/easy_cheese/shared/taste_test.py:662-802` constructs the typed document. | `tests/python/test_document_rules_compiler.py:76-199,225-283`; `tests/python/test_mold_taste_test.py:411-453` |
| Handback status | `src/easy_cheese_schemas/handback_status.py:15-178` defines names, reasons, dispositions, and errors. | `src/easy_cheese/shared/handoff.py:38-184` and `src/easy_cheese/shared/handoff_cli.py:29-109` parse, render, and expose them. | `tests/schemas/python/test_handback_status_contract.py:54-174,254-313` |
| Workflow commands | Schema models define each wire value above. | `src/easy_cheese/skills/mold/commands.py:31-42` exposes `migrate` and `publish`. `src/easy_cheese/skills/cook/commands.py:126-130` exposes `accept`. | `tests/python/test_contract_migrate.py:76-170`; `tests/python/test_cook_contract_accept.py:79-231` |

The focused schema and shared suites pass 257 tests.
The suites include producer model tests and consumer integration tests.
The bundle migration test exists, but this node does not rebuild or run bundles.

## Findings

### Blocker

- **Normalization changes valid payload text.** The schema declares `normalize_quotes` at `src/easy_cheese_schemas/contracts.py:623-634`. Shared treats all curly quotes as structure at `src/easy_cheese/shared/publication.py:132-168`. A probe changes the curly apostrophe in `don’t` to a straight apostrophe. Tests cover a curly key and straight-delimited content at `tests/python/test_publication_gateway.py:110-147`. They do not cover all-curly input. **Fix:** Identify paired structural delimiters. Preserve curly characters inside values. Reject ambiguous input. Add the probe as a regression test.
- **Replay ignores the schema-defined operation identity.** `HandoffPointer.operation_id` is required at `src/easy_cheese_schemas/contracts.py:680-692`. `_validate_replay` omits it at `src/easy_cheese/shared/publication.py:517-526`. A probe changes the stored value to `other`. Replay returns `operation_id=other` for the `op-probe` request. **Fix:** Compare both operation IDs before rehydration. Add a tampered-pointer regression test.

### High

- **Legacy source identities can disagree.** `NormalizationReceipt` never compares its two schema URI values at `src/easy_cheese_schemas/contracts.py:650-675`. Migration emits equal values at `src/easy_cheese/shared/migrate.py:103-117`. Publication checks only the canonical digest at `src/easy_cheese/shared/publication.py:480-489`. A direct runtime probe accepts different URI values. **Fix:** Require both URI values to match. Add model, gateway, and acceptance tests.
- **The emitted receipt schema accepts null legacy source values.** The runtime model rejects null at `src/easy_cheese_schemas/contracts.py:666-675`. The emitted schema allows null at `tests/schemas/python/goldens/normalization-receipt.json:1`. Shared uses runtime validation at `src/easy_cheese/shared/publication.py:480-485`. JSON Schema consumers and Shared therefore enforce different requirements. **Fix:** Make the conditional schema require non-null values. Add a JSON Schema regression test.
- **Shared reads an unbounded pointer before schema validation.** Schemas set `MAX_CONTRACT_BYTES` at `src/easy_cheese_schemas/contracts.py:16`. Shared calls `Path.read_bytes()` first at `src/easy_cheese/shared/publication.py:418-425`. **Fix:** Read at most `MAX_CONTRACT_BYTES + 1` bytes. Reject larger pointers before allocation. Add a size-boundary test.
- **Shared invents missing Grounding probes.** Schemas require each probe exactly once at `src/easy_cheese_schemas/contracts.py:2604-2617`. Shared creates two `unavailable` rows at `src/easy_cheese/shared/taste_test.py:681-689`. The accepted fixture omits Grounding at `tests/python/test_mold_taste_test.py:143-162,411-435`. Mold requires a prior record at `skills/mold/SKILL.md:62-64`. The parser cure in `.cheese/notes/r014-megamerge/re-review.md:85` remains incomplete. **Fix:** Pass the validated `MoldSpecDocument` into the taste gate. Remove the synthetic Grounding fallback. Add a missing-table rejection test.

### Medium

none

### Low

none

## STE100 status

compliant

Neither area has a `SKILL.md` file.
The direct area prose check does not apply.
I checked the endpoint prose at `skills/mold/SKILL.md:62-64,109-131` and `skills/cook/SKILL.md:30-36`.
The Grounding finding records the remaining prose mismatch.

## Follow-ups

- Repair quote normalization before publication.
- Bind replay to `operation_id`.
- Enforce one legacy source identity.
- Align the emitted receipt schema with runtime validation.
- Bound pointer reads before validation.
- Remove the synthetic Grounding fallback.
