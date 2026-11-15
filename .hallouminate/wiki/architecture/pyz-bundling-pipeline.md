# Pyz bundling pipeline

The pyz bundling pipeline uses Wedge to build self-contained `skills/<skill>/scripts/<skill>.pyz` archives.
`main` tracks no archive; the `publish dist` workflow commits them to `dist`, the default branch.
Running a skill does not download its archive.
The same files ship in default-branch installs, `dist` commit installs, and staged releases.[^1]

`tools/wedge/uv.lock` pins one Wedge commit.
Local builds, freshness checks, and CI use that tool project.
The separate tool project prevents Wedge's development dependency sources from replacing the published runtime dependencies.[^2]

## Discovery and source selection

Each Python-backed skill has a `wedge.toml` with `name`, `entry`, and `source_paths`.
Shared `skills/wedge.toml` supplies `source`, `include`, `project`, `groups`, and repository metadata.
Paths resolve relative to the skill directory; source selectors resolve beneath the source package.[^3]

Each source selection includes package initializers, `shared/`, `cli/`, and `skills/<own_python_slug>/`.
Wedge preserves those paths beneath `easy_cheese/`, including immutable resources.
Other skill packages do not enter the archive.
The schemas remain a complete included package.
There is no import-graph inference or private wheelhouse.[^3]

The runtime gate discovers Python skills from `src/easy_cheese/skills/*/commands.py`.
A test keeps this roster equal to the configured manifests.[^4]

## Dependencies and commands

The root project publishes `easy-cheese-schemas`.
Its schema dependencies and the `runtime` dependency group define the archive's third-party closure.
`uv.lock` pins that closure with hashes.
Wedge rejects incompatible wheels and installs with hash verification into a temporary build environment.[^5]

`requirements/runtime.txt` pins the corresponding test environment.
A test detects divergence from the exported lock.[^4]

Each archive dispatches only its own `COMMANDS`.
Dispatch resolves a selected command lazily, passes command-local arguments, and requires an integer status.
It does not mutate `sys.argv` or run source modules through `runpy`.[^6]

## Build and freshness check

`just wedge-build` invokes `wedge bundle --root skills`.
Wedge reuses its existing archive builder and writes executable `scripts/<name>.pyz` files.
It writes no launcher or sidecar lock.[^7]

Git ignores the built archives on `main`. A test fails when `main` tracks one.[^7]

Wedge uses reproducible Shiv output, strips volatile installation metadata, and normalizes ZIP members.
Its content digest covers member names and uncompressed bytes, not compressor-specific output.
Source-selection keys and build copies use the same selected files.[^2]

## Runtime startup

Run a skill directly:

```sh
python3 skills/<skill>/scripts/<skill>.pyz <subcommand>
```

The archive carries its runtime code and Python dependencies.
Shiv's transparent local cache extraction remains part of startup.
No Wedge launcher, sidecar lock, runtime package installation, or archive download is involved.[^1]

## Generated-runtime gates

`scripts/runtime_gates.py` checks generated phase registries, schema catalogs, document rules, and the bundle command index.
`just update-generated` rewrites those generated modules from their authoritative inputs.
Compiler programs remain under `scripts/` and do not enter archives.[^8]

The same gate validates every skill's declared command surface.
It also rejects obsolete shared-bundle references and cross-skill archive invocations.
The catalog gate imports contract modules normally so stale generated catalogs remain repairable.[^8]

## Tests and release staging

`just test` checks runtime inputs, then runs `just wedge-build` before any archive test.
The fixtures resolve stable archive paths; they do not build, cache, or select temporary archives.[^9]

The validation workflow builds the archives before its suites on pull requests, merge groups, and main.
`just check` and `just ci` inherit the build through `test`.[^10]

Focused pytest or browser commands use the archives on disk without rebuilding them.
After a fresh clone or a change to archive inputs, run `just wedge-build` before focused tests.[^9]

The release workflow builds the archives from the tagged commit.
`scripts/stage_release.py` then copies skill instructions, resources, and the built archives into the release tree.
It excludes runtime source and build configuration.
Staged execution tests use fresh caches outside the checkout.
A tagged release does not depend on a separate archive upload completing first.[^11]

## Local workflow

After changing archive inputs:

```sh
just update-generated  # when generated runtime inputs change
just wedge-build
just check
```

Do not commit the archives. On merge to `main`, `publish dist` builds them and appends one `dist` commit with the full tree plus archives.
See the [skill Python bundle doctrine](./skill-python-bundle-doctrine.md) for the dist contract.[^7]

## Superseded alternatives

PR #729 retires `scripts/build_pyz.py`, `scripts/check_bundles.py`, and the private-wheelhouse build pipeline.
The approved A correction restored committed archives without restoring that custom machinery.
PR #807 moved those committed archives from `main` to `dist`.[^1]

The initial Wedge migration proposed launchers, sidecar locks, and first-run downloads.
That deployment choice is rejected.
Option B, release-only self-contained archives, remains an assessment in [issue #732](https://github.com/paulnsorensen/easy-cheese/issues/732).

[^1]: AGENTS.md; https://github.com/paulnsorensen/easy-cheese/pull/729; https://github.com/paulnsorensen/easy-cheese/pull/807
[^2]: tools/wedge/pyproject.toml; tools/wedge/uv.lock
[^3]: skills/wedge.toml; skills/*/wedge.toml
[^4]: scripts/runtime_gates.py:`SKILLS`; tests/python/test_wedge_pin.py
[^5]: pyproject.toml; uv.lock
[^6]: src/easy_cheese/shared/bundle_commands.py; src/easy_cheese/skills/*/commands.py
[^7]: justfile:`wedge-build`, `test`, `check`, `ci`; .gitignore; tests/python/test_publish_dist.py
[^8]: scripts/runtime_gates.py; src/easy_cheese_schemas/_contract_modules.py; tests/python/test_generated_runtime_write.py
[^9]: tests/conftest.py; CONTRIBUTING.md; frontend/mold-review/tests/review.spec.js
[^10]: .github/workflows/validate.yml; justfile
[^11]: scripts/stage_release.py; tests/python/test_stage_release.py; .github/workflows/release.yml

_Source: user-approved A correction to PR #729 and the dist move in PR #807 · Updated: 2026-10-17 · Supersedes: launcher-and-lock distribution and the temporary test-archive pipeline; the custom wheelhouse builder remains retired._
