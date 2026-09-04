# Schemas to build edge review

## State

broken

The build compiles the schema package and reads its model registries.
One type declaration disagrees with the emitted phase data.
One generated reference omits defaults and required-field status.

## Evidence

### Schema producer

- `src/easy_cheese_schemas/contracts.py:68-87` returns sorted and unique `(slug, type)` pairs.
- `src/easy_cheese_schemas/_schema_catalog_compiler.py:17-24,34-53` converts those pairs into canonical schema URI constants.
- `src/easy_cheese_schemas/_schema_catalog.py:5-34` stores the compiled `frozenset[str]` URI registry.
- `src/easy_cheese_schemas/schema_runtime.py:65-88` checks the compiled catalog against the marked contract models.
- `src/easy_cheese_schemas/_phase_registry_compiler.py:32-35,92-225` requires every phase field and rejects invalid declarations.
- `src/easy_cheese_schemas/_phase_registry_compiler.py:329-350` emits `_compiled_phase_registry.py` from the phase YAML files.
- `src/easy_cheese_schemas/phase_contracts.py:50-102,169` exposes the immutable registry and its data projection.
- The projection emits `source`, `contract_version`, `input_schema_uris`, and `outputs`.
- Each output contains `destination` and `payload_schema_uri`.
- The version contains string values for `major`, `minor`, and `schema_uri`.
- `src/easy_cheese_schemas/contracts.py:1907-1920,1960-1967,2005-2015,2070-2091,2180-2192` defines writer defaults.
- `src/easy_cheese_schemas/contracts.py:2203-2214` maps each `WriterViewKind` to one payload type.
- `pyproject.toml:25-42` declares schema dependencies and excludes build-only compilers from the wheel.

### Build consumer

- `scripts/build_pyz.py:29-33,47-109` loads the schema compilers and the marked contract module.
- `scripts/build_pyz.py:112-154` rejects missing or stale generated schema sources.
- `scripts/build_pyz.py:294-317` builds the `easy-cheese-schemas` wheel.
- `scripts/build_pyz.py:320-350` binds the shared wheel to the same schema package version.
- `scripts/build_pyz.py:376-393` builds the schema wheel before shared and skill wheels.
- `scripts/build_pyz.py:541-586` reports build errors and returns exit status one.
- `scripts/render_generated_regions.py:35-38` imports contracts, the phase registry, and the schema URI registry.
- `scripts/render_generated_regions.py:188-260` reads document, writer, phase, model, and catalog registries.
- `scripts/render_generated_regions.py:71-73,308-333` emits three generated skill references.
- Those outputs are `curdle.md`, `writer-views.md`, and `schema-intertwine.md`.
- `justfile:15-30` checks generated references and runs both schema test suites.
- `justfile:37-39` installs runtime and build requirements before `scripts/build_pyz.py`.
- `.github/workflows/build-pyz.yml:7-29,61-78` builds bundles after schema or build source changes.

### Handoff and error contract

- No direct handoff artifact crosses this edge.
- Build packages `HandoffPointer` and other schema contracts without changing their fields.
- Phase declarations have no default fields.
- The phase compiler rejects missing fields, unknown fields, empty lists, invalid versions, and unknown schema URIs.
- Catalog compilation rejects invalid or duplicate generated constant names.
- Bundle compilation rejects missing or stale catalog, phase, and document-rule sources.
- Generated-reference check mode returns exit status one for drift.

### Test coverage

- `tests/schemas/python/test_schema_runtime.py:167-200` checks marker authority and exact catalog generation.
- `tests/schemas/python/test_phase_contracts.py:212-232,258-281,344-410` checks both generated registries and stale-source rejection.
- `tests/python/test_generated_regions.py:25-112` checks all schema-derived references and one real phase row.
- `tests/python/test_pyz_bundle.py:1154-1188` checks packaged catalog bytes and excludes compiler modules.
- The focused seam run passed 20 tests.
- `scripts/render_generated_regions.py --check` returned exit status zero.
- The tests exercise both sides, but they do not detect the two findings below.

### Skill prose

- The `schemas` and `build` areas do not contain `SKILL.md` files.
- This absence is expected because both areas are repository support code.
- `skills/cook/references/writer-views.md:3-11` is the user-facing schema projection on this edge.

## Findings

### Blocker

none

### High

none

### Medium

- **The build declares phase version numbers as integers.** `scripts/render_generated_regions.py:53-68` declares `major` and `minor` as `int`. The schema emits both values as `str` at `src/easy_cheese_schemas/phase_contracts.py:58-64,78-96`. The compiled data confirms the string values at `src/easy_cheese_schemas/_compiled_phase_registry.py:7-10`. A probe reported expected `int` values and actual `str` values. The cast at `scripts/render_generated_regions.py:206-208` hides the disagreement. **Fix:** Declare both fields as `str`. Add a test that checks every projected field type.
- **The generated writer reference does not show optional fields or defaults.** The schema defaults `deliverables` and `unresolved_work` to empty tuples at `src/easy_cheese_schemas/contracts.py:2180-2192`. The generated reference lists both as ordinary fields at `skills/cook/references/writer-views.md:47-51`. Its prose requires the shown payload shape at `skills/cook/references/writer-views.md:3-9`. The renderer prints only each field name and type at `scripts/render_generated_regions.py:151-165`. A probe showed that only `criterion_results` is required. The freshness test at `tests/python/test_generated_regions.py:31-46` preserves this omission. **Fix:** Mark fields with defaults as optional. Print each stable default. Compare the generated markers with the JSON Schema `required` lists.

### Low

none

## STE100 status

compliant

The reviewed areas have no `SKILL.md` files.
The reviewed generated prose follows the required sentence limits.

## Follow-ups

- Change `_ContractVersion.major` and `_ContractVersion.minor` to `str`.
- Render required markers and stable defaults from the schema model metadata.
- Add semantic tests for projected field types, required fields, and defaults.
