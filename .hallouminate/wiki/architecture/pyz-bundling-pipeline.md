# Pyz bundling pipeline

wedge builds every Python-backed skill as one content-addressed `.pyz` and publishes it as a GitHub release asset. The repository commits a launcher and a lock per skill, never the archive. wedge lives in `lib/` of github.com/paulnsorensen/skillz-that-grillz; `scripts/wedge.py` pins one commit of it, and `.github/workflows/wedge.yml` pins the same commit as a composite action.[^1]

## Discovery and configuration

Each Python-backed skill carries `skills/<skill>/wedge.toml`: `name` (the launcher file name), `entry` (`easy_cheese.skills.<package>.commands:main`), `source` (`src/easy_cheese`), `include` (`src/easy_cheese_schemas`), `project` (the repository root, which holds `pyproject.toml` and `uv.lock`), and `repo` (`paulnsorensen/easy-cheese`). `scripts/runtime_gates.py` derives `SKILLS` from `src/easy_cheese/skills/*/commands.py`, and a test keeps that roster equal to the set of `wedge.toml` files.[^2]

Each `commands.py` declares the application's public subcommands as an immutable `COMMANDS` tuple: every handler is a `@bundle_command("name")`-decorated function that imports its target lazily, and `derive_command(handler, summary)` compiles it into a `Command(name, "module:callable", summary)`. Dispatch validates unique command names, imports only the selected target, passes it a command-local `list[str]`, and requires an integer status return. Command targets write result text to stdout or diagnostics to stderr; dispatch does not mutate `sys.argv` or execute modules through `runpy`.[^12]

## Runtime closure

The root `pyproject.toml` is the published `easy-cheese-schemas` project. Its own dependencies (`attrs`, `cattrs`) plus the `runtime` dependency group (`fromargs`, which pulls the Cyclopts closure: `cyclopts`, `rich`, `rich-rst`, `pygments`, `markdown-it-py`, `mdurl`, `docstring-parser`) are pinned with hashes in `uv.lock`. `[tool.uv] default-groups = ["runtime"]` makes wedge's export (`uv export --frozen --no-dev --no-emit-project --no-emit-local`) include the group without adding it to the published wheel's dependencies. wedge refuses any wheel that is not `py3-none-any` and any dependency edge with a platform marker, then installs the closure with `uv pip install --no-cache --require-hashes --no-deps --target`, so every build downloads and hash-checks its wheels and a modified uv cache cannot reach an archive.[^3]

`requirements/runtime.txt` pins the same closure for the test and typing environments; `tests/python/test_wedge_pin.py` fails when the two drift.[^4]

Each archive vendors the whole `src/easy_cheese` package (`shared`, `cli`, and every skill package) beside `src/easy_cheese_schemas` and the third-party closure. It dispatches only its own skill's `COMMANDS`. Because the key covers every file under both trees, one change under `src/` changes every skill's lock.[^5]

## Build, key, and content digest

wedge runs shiv in reproducible mode with a fixed `SOURCE_DATE_EPOCH`, strips volatile install metadata (`RECORD`, `INSTALLER`, `REQUESTED`, `direct_url.json`, `__pycache__`, installed `bin/`), sorts and normalizes every ZIP member, and deflates the result. The lock pins two digests: the key, a sha256 over `wedge.toml`, `uv.lock`, and every file under `source` and `include`; and `content_sha256`, a sha256 over each member's name and uncompressed bytes. The content digest ignores the compressor, so a lock written on macOS matches the asset a Linux runner builds. The asset name embeds the digest: `<skill>-<content12>.pyz`.[^6]

`wedge lock` builds once, writes `skills/<skill>/scripts/<skill>.wedge.json`, and regenerates the launcher `skills/<skill>/scripts/<skill>` from wedge's template. `wedge check` recomputes the key and compares the launcher to the template without building; a stale lock or an edited launcher fails.

## Launcher

The launcher is stdlib-only Python. It reads the lock beside it, looks for the asset under `${WEDGE_CACHE:-${XDG_CACHE_HOME:-~/.cache}/wedge}/`, downloads it from `https://github.com/paulnsorensen/easy-cheese/releases/download/wedge/<asset>` when missing, verifies the content sha256, renames the download into the cache, and execs the archive with the same Python. Every later run verifies the cached copy before it runs. `WEDGE_PYZ` runs a local archive instead, still verified. Any mismatch prints one JSON line on stderr and exits 3 without running anything. Running a skill needs Python 3.11 or newer and network on first run; it needs neither shiv, pip, nor uv.[^7]

## Generated-runtime gates

`scripts/runtime_gates.py` owns the checks that used to run inside the Shiv build. Before any archive is built it recompiles the phase registry, schema catalog, document rules, and bundle command index in memory; any mismatch with the checked-in runtime modules fails with the path to regenerate. `--write-generated` (`just update-generated`) writes them instead. Compiler modules live under `scripts/` and never enter an archive.[^8]

The catalog recompile imports the contract modules normally. `easy_cheese_schemas._contract_modules.CONTRACT_MODULES` is the one inventory that both the runtime registry and the gate read. `schema_runtime` checks catalog staleness lazily: a cached accessor compares the registered contracts with `REGISTERED_CONTRACT_SCHEMA_URIS` on first catalog use, not at package import. This lets `runtime_gates.py --write-generated` import the package and repair a stale catalog. To add a contract module, add its dotted name to `CONTRACT_MODULES`; the gate needs no change.[^lazy-catalog]

The same script imports every selected `commands.py` from `src/` (refusing an `easy_cheese` that resolves anywhere else) and runs the dispatcher's own `validate_command_surface` and `command_map`, so an unreferenced declaration, an undeclared manifest entry, a duplicate name, or a manifest that fails to import stops the gate naming the skill. It also owns the cross-skill reference scan: a skill document or source that names another skill's launcher, any `<name>.pyz` token, a `common.pyz` mention, or a checked-in `skills/*/scripts/*.pyz` file is a violation.[^9]

## Tests

Tests execute a skill through its built archive, never through the committed launcher: the launcher trusts only the committed lock's digest, and a test must exercise the working tree. `scripts/skill_archives.py` returns `$EASY_CHEESE_PREBUILT_PYZ/<skill>.pyz` when `just test` or CI has built the set once, and otherwise builds the requested skill once per process through the pinned wedge. Suite conftests expose it as the `bundle` fixture.[^13]

## CI and release

`.github/workflows/wedge.yml` runs `wedge check` on every pull request and, after a push to `main`, builds each locked skill, compares the digest to the lock, and uploads any missing asset to the rolling `wedge` prerelease. Publication is append-only, so concurrent runs converge on one asset and the workflow carries no cancelling concurrency group. `validate.yml` runs `runtime_gates.py` and builds the archive set once before the pytest jobs.[^10]

The release workflow stages each skill's `SKILL.md`, launcher, and lock (no archive, no `wedge.toml`) onto the `release` branch through `scripts/stage_release.py`, which builds nothing. `gh skill install` receives the launcher; the asset it names was published when the commit landed on `main`.[^11]

## Local workflow

Running skills needs no setup beyond Python:

```sh
python3 skills/<skill>/scripts/<skill> <subcommand>
```

Relocking is explicit:

```sh
just wedge-lock    # rebuild every skill through the pinned wedge; rewrite locks and launchers
just wedge-check   # verify every lock is current and every launcher matches the template
```

`just check` and `just ci` run `wedge-check`; `just test` runs `runtime_gates.py`, builds the archive set once, and points every suite at it.[^14]

## Superseded pipeline

Until 2026-09-27 the repository committed each archive under `skills/<skill>/scripts/<skill>.pyz`, built by `scripts/build_pyz.py` from PEP 517 wheels in a private wheelhouse, checked for currency by `scripts/check_bundles.py`, and gated by `.github/workflows/build-pyz.yml` with shiv pinned in `requirements-build.txt`. The `pyz-pipeline-contracts` ADRs record that design. wedge replaced all of it; the generated-runtime and command-surface gates moved to `scripts/runtime_gates.py` unchanged.

[^1]: scripts/wedge.py; .github/workflows/wedge.yml; tests/python/test_wedge_pin.py
[^2]: skills/*/wedge.toml; scripts/runtime_gates.py:`SKILLS`
[^3]: pyproject.toml (`[dependency-groups]`, `[tool.uv]`); uv.lock
[^4]: requirements/runtime.txt; tests/python/test_wedge_pin.py:`test_runtime_requirements_match_the_uv_lock`
[^5]: skills/*/wedge.toml (`source`, `include`)
[^6]: skills/*/scripts/*.wedge.json
[^7]: skills/*/scripts/<skill> (generated launcher)
[^8]: scripts/runtime_gates.py:`GENERATED_RUNTIME_SOURCES`, `write_generated_runtime`
[^9]: scripts/runtime_gates.py:`validate_command_surfaces`, `check_skill_references`; tests/python/test_doctrine_topology.py
[^10]: .github/workflows/wedge.yml; .github/workflows/validate.yml
[^11]: .github/workflows/release.yml; scripts/stage_release.py; tests/python/test_stage_release.py
[^12]: src/easy_cheese/shared/bundle_commands.py; src/easy_cheese/skills/*/commands.py; tests/python/test_bundle_commands.py
[^13]: scripts/skill_archives.py; tests/*/python/conftest.py
[^14]: justfile
[^lazy-catalog]: scripts/runtime_gates.py:`_compiled_schema_catalog_source`; src/easy_cheese_schemas/schema_runtime.py:`_checked_registered_contracts`; src/easy_cheese_schemas/_contract_modules.py; tests/python/test_generated_runtime_write.py; tests/schemas/python/test_phase_contracts.py

_Source: implemented repository architecture · Updated: 2026-09-27 · Supersedes: the committed Shiv archives and the `build_pyz.py`/`check_bundles.py`/`build-pyz.yml` pipeline, committed internal-wheel hashes, inaccurate bundle-comparison wording, implicit command registration, and the literal `Command(...)` manifest form_
