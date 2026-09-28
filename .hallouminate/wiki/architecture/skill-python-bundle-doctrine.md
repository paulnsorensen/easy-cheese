# Skill Python bundle doctrine

Every Python-backed skill ships one committed, same-named `.pyz` archive.
Wedge builds the archive; it adds no runtime launcher, sidecar lock, or first-run download.
Runtime source stays under `src/`; skill archives are generated deployment files.[^1]

## Skill deployment contract

- A Python skill ships exactly `skills/<skill>/scripts/<skill>.pyz`.
- A skill without Python ships no Python archive.
- Skill prose invokes only its own archive, never loose source, repository automation, `common.pyz`, or another skill's archive.
- Hand-written Python never lives under `skills/`.
- Build configuration lives in each skill's `wedge.toml`, over shared `skills/wedge.toml`.
- Installed skill trees need the archive, not the build configuration.
- Markdown, templates, and other non-executable skill resources remain ordinary files.
- Wedge and Shiv are build dependencies only. Archive startup needs Python, not pip, uv, or network access.[^2]

## Source and package layout

Runtime Python uses two import packages:

```text
src/
├── easy_cheese/
│   ├── shared/
│   ├── cli/
│   └── skills/
│       └── <python_skill_name>/
└── easy_cheese_schemas/
```

`easy_cheese_schemas` is the independently published distribution.
Wedge copies selected local runtime packages directly; this build does not create internal application or shared-runtime wheels.[^3]

Skill slugs use kebab-case. Python package segments use underscores.
Skill-owned code lives in `src/easy_cheese/skills/<python_skill_name>/`.
Shared code lives in `src/easy_cheese/shared/`.
The `cli/` package owns command surfaces and reply presentation.
Tests stay under `tests/`; repository build and maintenance programs may live under `scripts/`.[^3]

## Per-skill runtime contents

Each archive contains:

1. its own skill package and immutable resources;
2. `easy_cheese.shared`, `easy_cheese.cli`, and required package initializers;
3. `easy_cheese_schemas`;
4. the pure-Python dependencies pinned by `uv.lock`.

Each manifest's `source_paths` selects local files beneath `src/easy_cheese` without flattening package paths.
It explicitly includes initializers, shared support, CLI support, and its own skill.
It does not include other skill packages or infer an import closure.[^4]

The root project's schema dependencies and `runtime` dependency group define the third-party closure.
`requirements/runtime.txt` pins the same closure for tests; a repository test detects drift.[^5]

## Zip-safe runtime

Archives may contain Python modules, bytecode, immutable package resources, and distribution metadata.
Dependencies must be platform-independent, pure Python, and zip-importable.

The following remain prohibited:

- native extensions and platform-specific libraries;
- required external executables as bundled dependencies;
- runtime package installation or archive downloads;
- caller-managed extraction before execution.

Shiv may extract its bundled environment into its transparent cache.
This local extraction does not download code or require caller-managed setup.[^2]

## Build enforcement

`just wedge-build` runs the pinned `wedge bundle` command.
It writes executable archives directly into their skill directories.
`just wedge-check` rebuilds temporarily and compares normalized archive contents without rewriting committed files.[^6]

Wedge exports the locked dependency closure, verifies wheel hashes, and builds reproducible archives.
The content comparison ignores compressor differences.
Selected source files and complete schema resources feed the build.
No easy-cheese custom ZIP writer, import-closure walker, or runtime loader is required.[^4]

`scripts/runtime_gates.py` checks generated sources, command surfaces, and skill-owned archive references.
Tests inspect archive membership and run staged archives without repository imports.
Release staging copies committed archives; it does not depend on a separate asset publication job.[^7]

## Command discovery and generated sources

Each skill declares its public surface in an immutable `COMMANDS` tuple.
Handlers use `@bundle_command`; `derive_command` produces the command records.
Dispatch imports the selected target lazily and passes command-local arguments.
Command targets return integer process statuses.[^8]

The runtime gate derives the skill roster from `src/easy_cheese/skills/*/commands.py`.
A test compares that roster with the skill manifests.
`just update-generated` repairs generated runtime modules.
`scripts/render_generated_regions.py` generates command inventories and schema-backed prose.
Edit generator inputs instead of generated regions.[^7]

## Decision and migration boundary

PR #729 replaces the repository's custom builder with Wedge, not its self-contained deployment model.
The approved A correction keeps archives in the main repository so branch and commit installs remain complete.
It rejects the proposed extensionless launchers, sidecar locks, rolling release assets, and first-run downloads.[^9]

Option B would keep archives only in versioned release trees.
[Issue #732](https://github.com/paulnsorensen/easy-cheese/issues/732) assesses B; it does not authorize migration.

The old private-wheelhouse builder remains retired.
The [Pyz bundling pipeline](./pyz-bundling-pipeline.md) records the current build and release flow.

[^1]: AGENTS.md; skills/*/wedge.toml
[^2]: skills/*/scripts/*.pyz; tools/wedge/uv.lock; AGENTS.md
[^3]: pyproject.toml; src/easy_cheese/; src/easy_cheese_schemas/
[^4]: skills/wedge.toml; skills/*/wedge.toml; tools/wedge/pyproject.toml
[^5]: pyproject.toml; uv.lock; requirements/runtime.txt; tests/python/test_wedge_pin.py
[^6]: justfile:`wedge-build`, `wedge-check`; .github/workflows/wedge.yml
[^7]: scripts/runtime_gates.py; scripts/skill_archives.py; scripts/stage_release.py; tests/python/test_stage_release.py
[^8]: src/easy_cheese/shared/bundle_commands.py; src/easy_cheese/skills/*/commands.py
[^9]: https://github.com/paulnsorensen/easy-cheese/pull/729; https://github.com/paulnsorensen/easy-cheese/issues/732

_Source: user-approved A correction to PR #729 · Updated: 2026-09-28 · Supersedes: proposed launcher-and-lock deployment and whole-runtime vendoring; the custom builder remains retired._
