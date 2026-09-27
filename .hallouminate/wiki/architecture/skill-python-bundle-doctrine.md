# Skill Python bundle doctrine

Every Python-backed skill ships one same-named wedge launcher and lock. wedge builds the skill's content-addressed archive from the repository project and publishes it as a release asset; the repository never commits the archive. Runtime source lives under `src/`; checked-in skill directories contain generated deployment files, not hand-written Python source. The repository conforms to this contract for every packaged Python skill.[^1]

## Skill deployment contract

- A skill that executes Python ships exactly the launcher `skills/<skill>/scripts/<skill>` and the lock `skills/<skill>/scripts/<skill>.wedge.json`, built from `skills/<skill>/wedge.toml`.
- A skill that does not execute Python ships no launcher.
- Skill prose invokes only its own launcher. It never invokes loose source, repository automation, `common.pyz`, or another skill's launcher.
- Hand-written Python never lives under `skills/`. `wedge lock` generates the launcher from wedge's template; nobody edits it. The archive is a release asset, never a committed file.
- Markdown, schemas, templates, and other non-executable resources remain ordinary skill files.
- wedge, and the shiv it pins, is a build dependency only. Running a skill requires Python 3.11 or newer and, on first run, network access to the `wedge` release. It requires neither shiv, pip, nor uv.[^2]

## Source and distribution layout

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

- `easy_cheese_schemas` is the independently published distribution.
- `easy-cheese-shared` is a repository-internal distribution containing the cohesive shared runtime package and the `cli` presentation layer.
- Each Python skill is a separate internal application distribution named `easy-cheese-<skill>`.
- Skill slugs stay kebab-case; Python package segments use underscores.
- Skill-owned code lives in `src/easy_cheese/skills/<python_skill_name>/`; its `commands.py` declares the console surface as an immutable tuple of `Command(name, "module:callable")` values.[^8]
- Every command target accepts only its command arguments as `list[str]`, writes result text to stdout or diagnostics to stderr, and returns an integer process status. Dispatch resolves the target lazily and calls it directly; it does not mutate `sys.argv`, execute a module through `runpy`, or depend on decorator registration.[^9]
- Shared code lives in `src/easy_cheese/shared/`.
- `src/easy_cheese/cli/` holds command surfaces and the JSON reply envelope. It may import `shared` and schemas. `shared` code must not import `cli`, except `resolve_cli`'s re-export of the envelope names.
- Tests stay under `tests/`; build, release, generation, and maintenance programs may live under `scripts/`.[^3]

Distribution dependencies carry the runtime relationship: each application depends on `easy-cheese-shared`, and shared depends on `easy-cheese-schemas`. Pip resolves that graph inside a private wheelhouse; no hand-maintained source closure map remains.[^4]

## Zip-safe runtime

Bundles may contain Python modules, bytecode, immutable package resources, and distribution metadata. All dependency wheels must be platform-independent pure Python.

The following remain prohibited:

- native extension modules such as `.so`, `.pyd`, and `.dylib`;
- platform-specific wheels;
- required external executables;
- runtime package installation, and any download other than the launcher's fetch of the skill's own locked archive;
- caller-managed extraction before a skill can run.

The launcher's first-run download and content verification, and Shiv's transparent cache extraction, are part of the archive runtime contract, not a caller responsibility. The launcher fetches the asset its lock names from the `wedge` release, verifies the content sha256, caches it under `${WEDGE_CACHE:-${XDG_CACHE_HOME:-~/.cache}/wedge}/`, and execs it with the same Python. `WEDGE_PYZ` points it at a local archive, still verified. Any mismatch prints one JSON line on stderr and exits 3. The archive then selects its cached environment and runs the packaged entry point.[^5]

## Runtime closure

Each bundle contains:

1. the whole `easy_cheese` package: `shared`, `cli`, and every skill package;
2. the `easy_cheese_schemas` package;
3. the pure-Python third-party closure that `uv.lock` pins: the schemas' dependencies plus the `runtime` dependency group (`fromargs` and its Cyclopts closure).

Shipping the whole runtime package is intentional. wedge vendors the `source` and `include` trees whole, and each archive dispatches only its own skill's `COMMANDS`. Excluding other skills' packages is no longer a build property; the dispatcher boundary and the reference scan in `scripts/runtime_gates.py` keep skills from calling each other. Because the key covers every file under `src/`, one change there changes every skill's lock.[^6]

## Build enforcement

wedge builds each archive, and the repository gates the inputs:

- `wedge build` exports the root project's non-dev closure (the `runtime` dependency group and the schemas' own dependencies) from `uv.lock` with hashes, refuses any wheel that is not `py3-none-any` or that carries a platform marker, and installs with `--no-cache --require-hashes --no-deps`;
- it vendors `src/easy_cheese` and `src/easy_cheese_schemas` whole, strips volatile install metadata, and normalizes every ZIP member before it computes the content digest;
- `wedge lock` writes the lock and regenerates the launcher from the template; `wedge check` recomputes the key from `wedge.toml`, `uv.lock`, and every file under `src/`, and fails on a stale lock or an edited launcher;
- `scripts/runtime_gates.py` verifies the checked-in generated schema and runtime sources, validates every skill's command surface, and rejects any `.pyz` token, `common.pyz` mention, cross-skill launcher reference, or checked-in archive;
- the post-merge publish job rebuilds every locked skill, compares the digest to the lock, and uploads only a missing asset;
- tests exercise each built archive with repository imports unavailable, through `scripts/skill_archives.py`, never through the committed launcher.[^7]

### Command discovery and generated regions (r014)

Skills declare commands only through `@bundle_command` and `derive_command` into an immutable `COMMANDS` tuple (`src/easy_cheese/shared/bundle_commands.py:20-58,108-127`); `validate_command_surface` rejects an undeclared or unreferenced name. Literal `Command(...)` construction is a rejected pattern. `scripts/check_bundles.py:461-499` once discovered only literal `Command(...)` calls and found zero commands in 11 of 13 archives, including every Wheypoint handler; it now imports the decorator path. The `runtime_gates.SKILLS` roster is a glob of `src/easy_cheese/skills/*/commands.py`, and a test keeps it equal to the set of `skills/*/wedge.toml`; it was once a hand-maintained list, not a scan of `src/easy_cheese/skills/*/` (#477 wave A1).

`src/easy_cheese_schemas` is the source of truth for catalog URIs, phase contracts, and document rules. `_schema_catalog_compiler.py` and `_phase_registry_compiler.py` compile them into `_schema_catalog.py` and `_compiled_phase_registry.py`; `scripts/render_generated_regions.py` projects the same models into `skills/mold/references/curdle.md`, `skills/cook/references/writer-views.md`, and `skills/cheese/references/schema-intertwine.md`. Never hand-edit a generated region; fix the generator and rerun it. `scripts/runtime_gates.py` exits `1` on stale or missing generated output, and `package.json` chains the docs generator before Astro with `&&`, so a generator error blocks the docs deploy. Two known renderer gaps: `writer-views.md` does not mark which fields have defaults, and `_ContractVersion.major`/`.minor` are declared `int` while the registry emits `str`. `document_rules.py` has no regeneration CLI; regenerate with `python3 -c "...b._compiled_document_rules_source()..."` because `runtime_gates.py` only detects staleness.

## Superseded topology

This doctrine supersedes the split runtime roots under `src/<skill>/` and `shared/scripts/`, multi-consumer `common.pyz` archives, cross-skill archive calls, `vendor_deps.py`, the custom ZIP writer, AST-based closure inference, and, since 2026-09-27, the committed Shiv archives with their `build_pyz.py` and `check_bundles.py` pipeline. [[pyz-bundling-pipeline]] records the implemented pipeline.

[^1]: AGENTS.md; skills/*/wedge.toml; tools/wedge/pyproject.toml
[^2]: tools/wedge/uv.lock; .github/workflows/wedge.yml
[^3]: src/easy_cheese/skills/; src/easy_cheese/shared/; src/easy_cheese_schemas/
[^4]: pyproject.toml (`[dependency-groups] runtime`); uv.lock; skills/wedge.toml (`groups`)
[^5]: skills/*/scripts/<skill> (generated launcher); AGENTS.md
[^6]: skills/wedge.toml (`source`, `include`); scripts/runtime_gates.py:`check_skill_references`; tests/python/test_doctrine_topology.py
[^7]: scripts/runtime_gates.py; scripts/skill_archives.py; tests/python/test_wedge_pin.py; .github/workflows/wedge.yml
[^8]: src/easy_cheese/shared/bundle_commands.py:`Command`; src/easy_cheese/skills/*/commands.py
[^9]: src/easy_cheese/shared/bundle_commands.py:`dispatch`; tests/python/test_bundle_commands.py

_Source: implemented repository architecture; r014 skill-review round notes (ingest hash 499c49c7b67d5eb6) for the command-discovery section · Updated: 2026-09-27 · Supersedes: committed Shiv archives and the `build_pyz.py`/`check_bundles.py` pipeline, committed internal-wheel hashes, split runtime roots, custom closure inference, vendored trees, shared common archives, and literal `Command(...)` discovery in `check_bundles.py`_
