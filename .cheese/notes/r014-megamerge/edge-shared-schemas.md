# Shared to Schemas Edge Review

## State

broken

Three high findings break this edge.

## Evidence

- Shared imports the contract models and adapter registry at `src/easy_cheese/shared/migrate.py:22-33`. Schemas exports these names at `src/easy_cheese_schemas/__init__.py:12-28,127-167,237-254`.
- Shared uses exact adapter lookup and sunset checks at `src/easy_cheese/shared/migrate.py:74-81`. Schemas defines those rules at `src/easy_cheese_schemas/compat.py:497-545`.
- Shared emits a canonical payload and a legacy receipt at `src/easy_cheese/shared/migrate.py:96-128`. Schemas defines the receipt fields at `src/easy_cheese_schemas/contracts.py:637-675`.
- Shared validates routes at `src/easy_cheese/shared/publication.py:463-478,566-571`. Schemas defines the immutable registry at `src/easy_cheese_schemas/phase_contracts.py:147-237`.
- The registry declares the `mold -> cook` Curd plan route at `src/easy_cheese_schemas/_compiled_phase_registry.py:69-84`.
- Shared writes payload, receipt, and pointer files at `src/easy_cheese/shared/publication.py:577-628`. Schemas defines their models at `src/easy_cheese_schemas/contracts.py:575-582,650-692`.
- Shared resolves and validates each referenced file at `src/easy_cheese/shared/publication.py:418-490`. Schemas bounds and verifies those files at `src/easy_cheese_schemas/artifacts.py:65-126,239-335,498-599`.
- Mold exposes `migrate` and `publish` at `src/easy_cheese/skills/mold/commands.py:31-42,66-94`. Its handler fixes the route and schema at `src/easy_cheese/skills/mold/contract_handlers.py:33-145`.
- Cook exposes `accept` at `src/easy_cheese/skills/cook/commands.py:126-130,189-235`. Its handler requires the Cook phase and Curd plan schema at `src/easy_cheese/skills/cook/contract_handlers.py:119-143`.
- Shared tests cover route identity, publication, replay, and receipt checks at `tests/python/test_publication_gateway.py:76-94,160-387`.
- Schema tests cover receipt fields and transition errors at `tests/schemas/python/test_contracts.py:1014-1073` and `tests/schemas/python/test_phase_contracts.py:498-532`.
- The focused run passed 53 tests and skipped 16 bundle tests. The skip guards require optional build tools at `tests/python/test_contract_migrate.py:26-31` and `tests/python/test_cook_contract_accept.py:25-30`.
- A direct migration probe produced a valid `mold -> cook` pointer. It also produced matching source fields and matching canonical digests.
- No `SKILL.md` file exists for the shared or schemas area. The Mold and Cook command prose agrees with the runtime seam at `skills/mold/SKILL.md:21-24,127-133` and `skills/cook/SKILL.md:30-36`.

## Findings

### Blocker

none

### High

- **Malformed legacy input escapes the command error contract.** Schemas defines a conversion callback at `src/easy_cheese_schemas/compat.py:409-425`. The built-in callback reads legacy keys directly at `src/easy_cheese_schemas/compat.py:434-484`. Shared calls the callback without a wrapper at `src/easy_cheese/shared/migrate.py:96-118`. Mold catches only named contract errors at `src/easy_cheese/skills/mold/contract_handlers.py:136-143`. A probe returned an uncaught `KeyError` for missing `curds`. **Fix:** Validate each legacy field before conversion. Wrap conversion failures in `UnsupportedLegacySourceError`. Add a malformed 0.9 command test.
- **A legacy receipt can contain two source identities.** The schema requires both fields but does not compare them at `src/easy_cheese_schemas/contracts.py:637-675`. Shared emits equal fields at `src/easy_cheese/shared/migrate.py:103-116`. Publication trusts the schema validator at `src/easy_cheese/shared/publication.py:480-489`. A probe changed the nested URI, and acceptance succeeded. The schema tests only remove fields at `tests/schemas/python/test_contracts.py:1029-1073`. **Fix:** Require `source_schema_uri == source_version.schema_uri`. Add model, runtime, migration, and acceptance tests.
- **The generated schema permits null legacy source values.** The conditional schema only requires field names at `src/easy_cheese_schemas/contracts.py:147-156,637-644`. The runtime validator rejects null values at `src/easy_cheese_schemas/contracts.py:660-675`. A probe found zero JSON Schema errors and one runtime rejection. **Fix:** Add non-null properties to the conditional schema. Add one test that runs both validators.

### Medium

none

### Low

none

## STE100 status

compliant

The relevant Mold and Cook prose uses short, active instructions. This note also complies with ASD-STE100.

## Follow-ups

- Fix the malformed legacy input error path.
- Enforce one source identity in each legacy receipt.
- Align null handling between the generated schema and runtime validation.
- Run the bundle command tests after the final bundle rebuild.
