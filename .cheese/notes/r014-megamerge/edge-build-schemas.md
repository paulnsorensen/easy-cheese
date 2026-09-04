# Build to Schemas Edge Review

## State

broken

Build reads schema models and compiled registries.
The generated references do not preserve the complete schema contract.

## Evidence

### Schemas producer

- `src/easy_cheese_schemas/contracts.py:85-87` returns the registered contract models.
- `src/easy_cheese_schemas/contracts.py:2203-2270` defines writer kinds, payload types, and mismatch errors.
- `src/easy_cheese_schemas/contracts.py:2487-2568` defines Mold sections, rules, fields, and defaults.
- `src/easy_cheese_schemas/phase_contracts.py:50-101` emits phase data through `TransitionRegistry.to_data()`.
- `src/easy_cheese_schemas/_schema_catalog.py:5-34` defines the canonical schema names and immutable URI set.
- `src/easy_cheese_schemas/_phase_registry_compiler.py:98-225` validates required fields, versions, schema names, and routes.
- `src/easy_cheese_schemas/__init__.py:127-254` exports the models, registry, and catalog that Build imports.

### Build consumer

- `scripts/render_generated_regions.py:35-38` imports `contracts`, `COMPILED_TRANSITION_REGISTRY`, and `REGISTERED_CONTRACT_SCHEMA_URIS`.
- `scripts/render_generated_regions.py:188-210` calls `MoldSpecDocument`, `writer_payload_types()`, `registered_contracts()`, and `to_data()`.
- `scripts/render_generated_regions.py:229-260` reads every phase handoff field and every registered schema URI.
- The handoff fields are `source`, `contract_version`, `input_schema_uris`, `outputs`, `destination`, and `payload_schema_uri`.
- `scripts/build_pyz.py:29-109` loads the schema contract and all three private compiler modules.
- `scripts/build_pyz.py:112-154` compares compiled output with the catalog, phase registry, and document rules.
- `scripts/build_pyz.py:294-393` builds the schema wheel and adds it through each shared dependency.
- `scripts/check_bundles.py:103-108,622-633` treats `easy_cheese_schemas` as a first-party archive namespace.

### Emitted files and commands

- `scripts/render_generated_regions.py:71-84,308-332` writes three schema-derived references.
- It writes `skills/mold/references/curdle.md` and `skills/cook/references/writer-views.md`.
- It also writes `skills/cheese/references/schema-intertwine.md`.
- `scripts/build_pyz.py:490-527` emits schema-bearing wheels and skill archives outside the Schemas source directory.
- Build emits no handoff artifact and writes no file under `src/easy_cheese_schemas`.
- `justfile:15-24` checks generated references and runs schema tests.
- `justfile:37-40,98-109` builds archives and checks their contents.
- `scripts/render_generated_regions.py:97-105,336-348` raises marker errors and returns one for drift.
- `scripts/build_pyz.py:112-154,560-586` rejects missing or stale runtime files and returns one.

### Contract changes and tests

- The new Grounding models appear at `contracts.py:2338-2356,2561-2568`.
- The generated Mold reference includes those models at `curdle.md:166-169,200-210,237-239`.
- No changed model or registry name is missing from the generated references.
- Build tests cover reference drift at `tests/python/test_generated_regions.py:25-112`.
- Schema tests cover compiler inputs and stale output at `tests/schemas/python/test_phase_contracts.py:124-232,284-410`.
- Schema tests reject a wrong writer kind at `tests/schemas/python/test_workflow_thread.py:727-755`.
- Bundle tests verify packaged schema files at `tests/python/test_pyz_bundle.py:1154-1188`.
- The focused compiler and reference suite passed 60 tests.
- The archive seam passed four tests when the command loaded `requirements-build.txt`.

## Findings

### Blocker

none

### High

- The writer reference omits the kind-to-payload mapping, optional fields, defaults, and conditional requirements. `contracts.py:2203-2270` maps each kind and rejects mismatches. `contracts.py:1840-1920,1933-2214` declares defaults and conditional validation. `writer-views.md:14-149` renders plain fields and one unmapped `WriterPayload` name. A writer can follow the reference and produce a payload that the host rejects. Tests compare bytes at `test_generated_regions.py:31-46`, but they do not compare schema meaning. **Fix:** Render the kind mapping. Mark optional fields and show defaults. Render conditional requirements. Add a semantic test against `schema_bytes()`.
- The normal test command skips the bundle seam. `justfile:2,15-31` omits `requirements-build.txt`. `test_pyz_bundle.py:27-31` then skips every bundle integration test. `build-pyz.yml:61-78` runs the seam with build dependencies. Its filters at `build-pyz.yml:7-29` omit `tests/python/test_pyz_bundle.py`. A test-only regression can merge without this workflow. **Fix:** Add build requirements to the main test environment. Add bundle test paths to the specialized workflow.

### Medium

- `_ContractVersion` declares `major` and `minor` as `int` at `render_generated_regions.py:53-56`. `TransitionRegistry.to_data()` emits both values as `str` at `phase_contracts.py:78-97`. The runtime probe confirmed that both values are strings. The cast at `render_generated_regions.py:208` hides this mismatch. **Fix:** Declare both fields as `str`. Add a test for the phase data field types.
- Build rejects stale runtime files but provides no generation command. `build_pyz.py:112-154` asks the caller to regenerate each stale file. `build_pyz.py:541-586` exposes only bundle output. `render_generated_regions.py:308-332` writes skill references and no runtime file. `justfile:37-40,93-103` exposes no registry generation command. Schemas changes therefore require an undocumented manual write. **Fix:** Add one command that writes all generated runtime files. Use the same render functions for write and check modes.

### Low

- `skills/cook/SKILL.md:123` says the Markdown reference generates schemas. The script generates the reference at `render_generated_regions.py:197-199,308-319`. The schema runtime validates JSON at `schema_runtime.py:260-300`. **Fix:** Name the script as the generator. Name the schema runtime as the validator.

## STE100 status

- No `skills/build/SKILL.md` or `skills/schemas/SKILL.md` exists.
- `skills/cook/SKILL.md:123-124` and `skills/mold/SKILL.md:146` contain the linked skill prose.
- `skills/mold/references/curdle.md:158` needs a complete active sentence.
- All other reviewed edge prose complies.
- This note complies.

## Follow-ups

- Make generated writer references preserve mappings, optional fields, defaults, and conditional requirements.
- Run bundle seam tests in the normal test command and for bundle test changes.
- Change `_ContractVersion.major` and `_ContractVersion.minor` to `str`.
- Add one supported command that writes all generated runtime files.
- Correct the generator ownership sentence and the Mold reference fragment.
