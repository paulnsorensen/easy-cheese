# Schemas review

## Verdict

reject

## Findings

### Blocker

none

### High

- **[correctness, contract] Legacy receipts permit two source identities.** `src/easy_cheese_schemas/contracts.py:637-675` checks presence but not equality. A probe passed different values for `source_schema_uri` and `source_version.schema_uri` through `validate_contract`. Fix: Validate equality, or remove the duplicate URI field.
- **[correctness, contract] The published receipt schema accepts null legacy source values.** `src/easy_cheese_schemas/contracts.py:145-156` requires only the field names. The properties remain nullable at `tests/schemas/python/goldens/normalization-receipt.json:1`. `Draft202012Validator` reports zero errors for this legacy receipt. Fix: Reject null values in the conditional schema and add a semantic schema test.

### Medium

- **[correctness, spec] Mini-spec normalization records probes that did not occur.** `src/easy_cheese/skills/mold/validate_spec.py:617-632` creates two `unavailable` Grounding rows when the source omits Grounding. `skills/mold/references/mini-spec-mode.md:12-27` defines that omission as the strict mini-spec format. Fix: Model the source-specific omission instead of creating false `unavailable` results.

### Low

- **[spec, deslop] Guard rules use tracer-only names and descriptions.** The validator applies blank matrix cells to both modes at `src/easy_cheese_schemas/contracts.py:2432-2441`. The generated metadata names only tracer mode at `src/easy_cheese_schemas/contracts.py:2482-2484,2522-2524`. Curdle documents both modes at `skills/mold/references/curdle.md:98-107`. Fix: Use one non-matrix rule name and description for both modes.
- **[spec, deslop] Comments and tests retain retired source paths.** Evidence appears at `src/easy_cheese_schemas/compat.py:10`, `src/easy_cheese_schemas/contracts.py:2278`, and `src/easy_cheese_schemas/wheypoint.py:551`. More evidence appears at `tests/python/test_schemas_types.py:4` and `tests/python/test_validate_spec.py:1`. The fixture command names a missing file at `tests/python/fixtures/spec_format/valid_spec.md:72`. Fix: Replace each retired path with its current package path.

## Simplifications

- `NormalizationReceipt` stores the source schema URI twice. Remove one field if the compatibility contract permits this change.
- Rename `tracer-row-blank-matrix-cells` for both non-matrix modes. This change removes duplicate terminology across code and generated rules.
- No other helper removal or library replacement is justified. The small helpers isolate schema rules, conversions, or bounded artifact operations.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `schemas -> shared` | broken | Shared accepts the contradictory receipt through `src/easy_cheese/shared/publication.py:480-489` and `contracts.py:637-675`. |
| `shared -> schemas` | ok | Migration and publication import the declared models and registries at `src/easy_cheese/shared/migrate.py:22-33` and `publication.py:463-489`. |
| `schemas -> mold` | broken | The model requires Grounding rows at `contracts.py:2450-2532`, but mini-spec normalization creates false rows at `validate_spec.py:617-632`. |
| `mold -> schemas` | broken | Mold constructs `MoldSpecDocument` at `validate_spec.py:627-632`, but its strict mini-spec path changes missing evidence into false evidence. |
| `schemas -> wheypoint` | ok | The schema defines compaction and revision fields at `src/easy_cheese_schemas/wheypoint.py:408-480,672-706`. |
| `wheypoint -> schemas` | ok | Wheypoint imports and checks these records at `src/easy_cheese/skills/wheypoint/commit.py:49-64` and `lineage.py:9-124`. |
| `build -> schemas` | ok | The build reads contract, catalog, registry, and rule sources at `scripts/build_pyz.py:29-33,63-103`. |
| `schemas -> build` | ok | `justfile:2,20` installs pinned requirements and checks generated regions. The generated-region check passes. |

## Verification

- The scoped suite passes all 446 tests.
- `scripts/render_generated_regions.py --check` passes.
- The receipt mismatch probe passes runtime validation.
- The legacy null probe produces zero JSON Schema errors.
- The strict mini-spec probe accepts a source without Grounding.

## STE100 status

compliant
