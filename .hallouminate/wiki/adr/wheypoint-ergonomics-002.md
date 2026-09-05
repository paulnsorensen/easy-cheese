# Wheypoint schema types live in the contract catalog module

<certain> Wheypoint's schema types move into `src/easy_cheese_schemas/contracts.py` and carry `@contract` markers; `easy_cheese_schemas/wheypoint.py` is deleted.[^spec]

## ADR-002: Move the types rather than teach the scanner [status: accepted]

- **Context:** <certain> The JSON Schema catalog registers only classes carrying `@contract` found in `contracts.py`'s own globals (`src/easy_cheese_schemas/contracts.py:68-82`), and a stale-catalog guard raises at import when registered URIs drift (`schema_runtime.py:84-86`). No wheypoint type was registered, so a `schema <name>` verb had nothing to print and agents had to unzip the bundle or guess the delta shape (#609).
- **Decision:** Move the 743 lines of wheypoint types into `contracts.py`, mark `CheckpointIntent` and its record types with `@contract`, regenerate the catalog with `just update-generated`, update the barrel re-export and the two tests that name the module, and delete the module. The user chose this over the scanner change.
- **Alternatives:** Teach `_registered_contracts()` to walk a module list (about ten lines, no file move). Rejected by the user; recorded in `.cheese/.out-of-scope/wheypoint-ergonomics-001.md`.
- **Consequences:** `contracts.py` grows to about 3,400 lines, but stays a barrel with no local imports. The published schemas package exposes wheypoint types from the same module as every other contract. Any future contract must live in `contracts.py` too.

## References

[^spec]: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/wheypoint-ergonomics.md`, approved 2026-09-05 — fork `F2-catalog`, AC-12, AC-22.
