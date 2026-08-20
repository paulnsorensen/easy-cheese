# Pyz bundling pipeline

How per-skill `.pyz` bundles are built, gated, and verified. Rederived 2026-08-17 from a full trace; recorded because no wiki page covered it.

## Build (`scripts/build_pyz.py`)

One self-contained zipapp per skill, deployed to `skills/<skill>/scripts/<skill>.pyz`. Four layers:

1. **Hand-authored registries** — `SKILLS` (subcommand → source script; generated `__main__.py` dispatches via `runpy`), `EXTRA_MODULES` (cross-src-dir imports the scanner cannot see), `PACKAGE_TREES` (whole packages, i.e. `easy_cheese_schemas`), `SRC_DIRS` (ultracook → `src/fanout/`). Subcommand registration is **manual** — see `.agents/skills/python-authoring/SKILL.md`.
2. **AST inference** — `needed_shared` / `_local_skill_modules` compute the transitive import closure over `shared/scripts/` and flat skill-dir siblings. Flat modules only; packages must be declared in `PACKAGE_TREES`.
3. **Generated-file gates** — every build recompiles in-memory and raises `RuntimeError` on mismatch with the checked-in copies:
   - `contracts.py` `@contract` / `@schema_constraints` decorators → `_schema_catalog_compiler.collect/render` → `_schema_catalog.py` (decorator derivation landed in #417 / `999ced85`; it covers the **schema catalog only**, not subcommand registration).
   - `skills/*/phase-contract.yaml` → `_phase_registry_compiler` → `_compiled_phase_registry.py`.
   Regeneration is manual: run the build, commit the output. No pre-commit hook; CI is the enforcement point.
4. **Deterministic packaging** — pinned zip timestamp/perms/entry order/compresslevel; `__pycache__` and the compiler modules excluded. `vendor_deps.py` (`vendor/`, stamp = sha256 of `requirements-vendor.txt`, attrs+cattrs wheels, hash-pinned) must be populated first via `just vendor`.

## Currency check (CI)

`check .pyz bundles are current` in `.github/workflows/build-pyz.yml` (ubuntu, py3.12): vendor → full rebuild → `scripts/check_bundles.py`.

**`check_bundles.py` is not a byte compare.** It compares each archive member's name + CRC32 + uncompressed size against `git show HEAD:<path>`, deliberately ignoring compressed bytes because `ZIP_DEFLATED` output differs between stock zlib and zlib-ng (`check_bundles.py:7-16`, `build_pyz.py:38-41`). A red check therefore always means genuine staleness (source changed without rebuild, or a stale generated file made `build_pyz` raise) — never environment/zlib variance. Byte determinism is asserted separately by `test_the_wheypoint_bundle_is_deterministic`.

A second workflow step asserts the bundled `easy_cheese_schemas.__version__` inside `ultracook.pyz` matches `pyproject.toml`.

## Safety nets for missing modules

- `tests/python/test_pyz_bundle.py::test_subcommand_resolves_inside_bundle` — every `(skill, subcommand)` run as `python <pyz> <sub> --help` in a `PYTHONPATH`-stripped subprocess; catches any missing top-level import.
- ~30 test sites import real logic from `cached_bundle(skill)` artifacts rather than `src/`.
- Residual gap: an undeclared cross-dir import deferred into a function body escapes both the build and the `--help` smoke test.

## Known friction

Nothing local enforces bundle currency: `just check` does not run `check_bundles.py` and there is no pre-commit hook, so "bundles stale" CI failures recur on PRs that touch `src/` without `just bundle` (e.g. #424).
