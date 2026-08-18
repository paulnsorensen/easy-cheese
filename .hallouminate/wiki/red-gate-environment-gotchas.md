# red-gate environment gotchas

Field notes from running the Cut→Cook gate end-to-end on the pyz-pipeline-contracts spec (2026-08). Each cost real diagnosis time; none is visible from the red_gate code alone.

## node_modules breaks phase snapshotting

`red-gate begin`/`issue`/`validate` walk the full project tree and refuse directory symlinks. pnpm's `node_modules/.pnpm` layout contains ~1500 of them, so **any red-gate operation fails while node_modules exists**. node_modules is gitignored and fully regenerable (`just docs-install`, frozen lockfile), so the working procedure is:

1. Delete node_modules before entering a Cut/Press phase or replaying a receipt.
2. Run Astro/pnpm gates (docs-build, tests needing node deps) **after** the last red-gate call of the session.

A durable fix would add `node_modules` to `_EXCLUDED_SNAPSHOT_DIRS` in `src/cut/red_gate.py` — not done as of this note because it changes receipt semantics.

## Cut production_paths: declare the blast radius you cannot see yet

Everything outside `production_paths` is frozen as an oracle dependency; `validate --state green` flags any drift. Two classes of paths are easy to under-declare:

- **`.gitignore`** — any restructure that moves gitignored generated outputs (e.g. Astro `src/` → `website/`) must rename ignore rules, so declare `.gitignore` whenever a spec moves directories.
- **Every test suite whose conftest imports `build_pyz` or loads modules from a bundle** — pruning a registry entry ripples into `tests/schemas/python` (bundle-provenance assertions, validator fixtures), not just the suites that obviously test the pruned thing. Grep `import build_pyz` and `cached_bundle(` across `tests/**` before fixing the path list.

The pyz-pipeline-contracts receipt carries exactly four green-validation variances from this (`.gitignore` + three `tests/schemas/python` files), each documented in `.cheese/cook/pyz-pipeline-contracts.md`.

## Pruning a subcommand is not pruning a module

`press.pyz red-gate` was removed as a *dispatchable subcommand*, but `src/fanout/press_route.py` still imports `cut.red_gate` at runtime, so `EXTRA_MODULES["press"]` must keep staging `red_gate.py` + `gate_receipts.py` + `taste_test.py` as plain modules. Before deleting a registry entry, distinguish its two roles: dispatcher surface (what the SKILLS map grants) vs staged import graph (what other staged files need).
