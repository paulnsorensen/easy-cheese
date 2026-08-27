# Pyz bundling pipeline

The repository builds every Python-backed skill as a hash-locked Shiv application from PEP 517 wheels. Shiv is installed only in bundle-building jobs or an explicit local build environment; consumers run the resulting archive with Python alone.[^1]

## Discovery and package graph

`scripts/build_pyz.py` discovers applications from `src/easy_cheese/skills/*/commands.py`. Each discovered package becomes one `easy-cheese-<skill>` wheel with a same-named console script.[^2]

A build creates three distribution layers:

1. `easy-cheese-schemas` from the root Hatchling project;
2. `easy-cheese-shared` from `src/easy_cheese/shared/`, depending on schemas;
3. one skill application from `src/easy_cheese/skills/<skill_name>/`, depending on shared.

Temporary Hatchling projects express the internal dependencies in standard `pyproject.toml` metadata. Pip, not an AST scanner or source registry, owns the transitive closure. A skill archive therefore receives its application, shared, schemas, and approved external wheels, while other skill applications stay out.[^3]

## Private wheelhouse

Each build creates a temporary private wheelhouse containing:

- the schema wheel;
- the shared internal wheel;
- the selected application wheels;
- external runtime wheels downloaded from `requirements/runtime.txt`.

The runtime lock is version- and hash-pinned. Downloads require wheels and hashes. Every wheel is rejected unless its filename is `py3-none-any`, its WHEEL metadata declares `Root-Is-Purelib: true`, and it contains no `.so`, `.pyd`, or `.dylib` member.[^4]

## Per-skill locks

Pip performs a dry-run install of `easy-cheese-<skill>==<version>` using only the private wheelhouse. The resulting report is converted into `requirements/bundles/<skill>.txt`, with an exact version and SHA-256 hash for every resolved wheel.[^5]

Normal builds compare the computed closure and hashes with the checked-in lock and fail if it differs. `scripts/build_pyz.py --update-locks` is the explicit regeneration path after a source, metadata, or runtime dependency change.

## Shiv assembly

For each application, the builder invokes Shiv with:

- the skill's console script;
- `--no-index` and `--find-links <wheelhouse>`;
- `--only-binary=:all:`;
- `--require-hashes`;
- `--reproducible`;
- `--uncompressed`;
- a `/usr/bin/env python3` interpreter line.

The output is written to `skills/<skill>/scripts/<skill>.pyz` and marked executable. At runtime, the archive manages Shiv's cache extraction transparently and dispatches the packaged console script. Shiv itself is not imported from the application and need not exist on the consumer machine.[^6]

## Generated-runtime gates

Before building wheels, the builder recompiles the phase registry, schema catalog, and document rules in memory. Any mismatch with the checked-in runtime modules stops the build. Compiler modules are excluded from the published schema wheel.[^7]

## CI and release

`.github/workflows/build-pyz.yml` is the dedicated bundle job. It installs `requirements-build.txt`, installs the runtime/test dependencies, rebuilds every archive without updating locks, compares rebuilt archive members with `HEAD`, and runs bundle isolation tests. Regular validation installs no Shiv.[^8]

`scripts/check_bundles.py` compares member names, CRCs, and uncompressed sizes rather than raw ZIP bytes. It ignores Shiv bootstrap metadata, console wrappers, and RECORD files whose bytes can vary with the host toolchain while retaining source-staleness detection.[^9]

The release workflow installs the same build-only requirements and runs `scripts/stage_release.py`. The staged tree contains skill files and one same-named archive per Python skill, with no loose Python source.[^10]

## Local workflow

Running skills needs no setup beyond Python:

```sh
python3 skills/<skill>/scripts/<skill>.pyz <subcommand>
```

Rebuilding archives is explicit:

```sh
python3 -m pip install -r requirements-build.txt
python3 scripts/build_pyz.py --update-locks  # when locks must change
just bundle                                # when current locks already match
```

`just check` resolves normal test dependencies from `requirements/runtime.txt` through uv and does not install Shiv. The GitHub bundle job remains the authoritative full rebuild gate.[^11]

[^1]: requirements-build.txt; CONTRIBUTING.md
[^2]: scripts/build_pyz.py:`SKILLS`
[^3]: scripts/build_pyz.py:`_project_toml`, `build_wheelhouse`
[^4]: requirements/runtime.txt; scripts/build_pyz.py:`validate_pure_wheel`, `_download_runtime_wheels`
[^5]: scripts/build_pyz.py:`_resolved_requirements`, `_requirements_for`; requirements/bundles/
[^6]: scripts/build_pyz.py:`_shiv_command`, `_build_from_wheelhouse`
[^7]: scripts/build_pyz.py:`_validate_generated_runtime`; pyproject.toml
[^8]: .github/workflows/build-pyz.yml; .github/workflows/validate.yml
[^9]: scripts/check_bundles.py
[^10]: .github/workflows/release.yml; scripts/stage_release.py
[^11]: justfile; .github/workflows/build-pyz.yml
