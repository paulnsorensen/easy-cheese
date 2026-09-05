# Skill Python bundle doctrine

Every Python-backed skill ships one same-named Shiv archive built from standard package metadata. Runtime source lives under `src/`; checked-in skill directories contain deployment artifacts, not Python source. The repository conforms to this contract for every packaged Python skill.[^1]

## Skill deployment contract

- A skill that executes Python ships exactly `skills/<skill>/scripts/<skill>.pyz`.
- A skill that does not execute Python ships no `.pyz`.
- Skill prose invokes only its own archive. It never invokes loose source, repository automation, `common.pyz`, or another skill's archive.
- Python source never lives under `skills/`. Checked-in archives are generated release artifacts.
- Markdown, schemas, templates, and other non-executable resources remain ordinary skill files.
- Shiv is a build dependency only. Running an archive requires Python, not Shiv or pip.[^2]

## Source and distribution layout

Runtime Python uses two import packages:

```text
src/
├── easy_cheese/
│   ├── shared/
│   └── skills/
│       └── <python_skill_name>/
└── easy_cheese_schemas/
```

- `easy_cheese_schemas` is the independently published distribution.
- `easy-cheese-shared` is a repository-internal distribution containing the cohesive shared runtime package.
- Each Python skill is a separate internal application distribution named `easy-cheese-<skill>`.
- Skill slugs stay kebab-case; Python package segments use underscores.
- Skill-owned code lives in `src/easy_cheese/skills/<python_skill_name>/`; its `commands.py` declares the console surface as an immutable tuple of `Command(name, "module:callable")` values.[^8]
- Every command target accepts only its command arguments as `list[str]`, writes result text to stdout or diagnostics to stderr, and returns an integer process status. Dispatch resolves the target lazily and calls it directly; it does not mutate `sys.argv`, execute a module through `runpy`, or depend on decorator registration.[^9]
- Shared code lives in `src/easy_cheese/shared/`.
- Tests stay under `tests/`; build, release, generation, and maintenance programs may live under `scripts/`.[^3]

Distribution dependencies carry the runtime relationship: each application depends on `easy-cheese-shared`, and shared depends on `easy-cheese-schemas`. Pip resolves that graph inside a private wheelhouse; no hand-maintained source closure map remains.[^4]

## Zip-safe runtime

Bundles may contain Python modules, bytecode, immutable package resources, and distribution metadata. All dependency wheels must be platform-independent pure Python.

The following remain prohibited:

- native extension modules such as `.so`, `.pyd`, and `.dylib`;
- platform-specific wheels;
- required external executables;
- runtime package installation or downloads;
- caller-managed extraction before a skill can run.

Shiv's transparent cache extraction is part of the archive runtime contract, not a caller responsibility. The archive launches itself, selects its cached environment, and runs the packaged console script.[^5]

## Runtime closure

Each bundle contains:

1. one skill application distribution;
2. the cohesive internal shared distribution;
3. the schema distribution;
4. approved pure-Python third-party distributions.

Shipping the full shared distribution is intentional. Shared is one internal dependency boundary, and metadata-driven installation removes the custom AST scanner, exception registries, and repeated closure maintenance that previously selected individual shared modules. Other skill application distributions remain excluded, and tests assert that boundary.[^6]

## Build enforcement

The build must:

- construct every internal distribution through PEP 517;
- resolve dependencies only from the private wheelhouse;
- require hashes from the committed external lock when populating the wheelhouse and from an ephemeral complete closure when assembling each bundle;
- reject non-`py3-none-any` wheels, false `Root-Is-Purelib` metadata, and native members;
- produce one same-named archive per discovered `commands.py`;
- verify checked-in generated schema/runtime sources;
- exercise bundled interfaces without repository imports or ambient site packages;
- compare rebuilt archive member names, CRCs, and sizes with the committed artifacts.[^7]



### Command discovery and generated regions (r014)

Skills declare commands only through `@bundle_command` and `derive_command` into an immutable `COMMANDS` tuple (`src/easy_cheese/shared/bundle_commands.py:20-58,108-127`); `validate_command_surface` rejects an undeclared or unreferenced name. Literal `Command(...)` construction is a rejected pattern. `scripts/check_bundles.py:461-499` once discovered only literal `Command(...)` calls and found zero commands in 11 of 13 archives, including every Wheypoint handler; it now imports the decorator path. The `build_pyz.SKILLS` roster is still a hand-maintained list, not a scan of `src/easy_cheese/skills/*/` (#477 wave A1).

`src/easy_cheese_schemas` is the source of truth for catalog URIs, phase contracts, and document rules. `_schema_catalog_compiler.py` and `_phase_registry_compiler.py` compile them into `_schema_catalog.py` and `_compiled_phase_registry.py`; `scripts/render_generated_regions.py` projects the same models into `skills/mold/references/curdle.md`, `skills/cook/references/writer-views.md`, and `skills/cheese/references/schema-intertwine.md`. Never hand-edit a generated region; fix the generator and rerun it. `build_pyz.py --check` exits `1` on stale or missing generated output, and `package.json` chains the docs generator before Astro with `&&`, so a generator error blocks the docs deploy. Two known renderer gaps: `writer-views.md` does not mark which fields have defaults, and `_ContractVersion.major`/`.minor` are declared `int` while the registry emits `str`. `document_rules.py` has no regeneration CLI; regenerate with `python3 -c "...b._compiled_document_rules_source()..."` because `just bundle` only detects staleness.

## Superseded topology

This doctrine supersedes the split runtime roots under `src/<skill>/` and `shared/scripts/`, multi-consumer `common.pyz` archives, cross-skill archive calls, `vendor_deps.py`, the custom ZIP writer, and AST-based closure inference. [[pyz-bundling-pipeline]] records the implemented pipeline.

[^1]: AGENTS.md; scripts/build_pyz.py
[^2]: requirements-build.txt; .github/workflows/build-pyz.yml
[^3]: src/easy_cheese/skills/; src/easy_cheese/shared/; src/easy_cheese_schemas/
[^4]: scripts/build_pyz.py:`_project_toml`, `_build_shared_wheel`, `_build_skill_wheel`
[^5]: scripts/build_pyz.py:`_shiv_command`; AGENTS.md
[^6]: tests/python/test_pyz_bundle.py:`test_bundle_carries_only_its_own_skill_package`, `test_briesearch_bundle_uses_internal_distributions`
[^7]: scripts/build_pyz.py:`validate_pure_wheel`; scripts/check_bundles.py; tests/python/test_pyz_bundle.py
[^8]: src/easy_cheese/shared/bundle_commands.py:`Command`; src/easy_cheese/skills/*/commands.py
[^9]: src/easy_cheese/shared/bundle_commands.py:`dispatch`; tests/python/test_bundle_commands.py

_Source: implemented repository architecture; r014 skill-review round notes (ingest hash 499c49c7b67d5eb6) for the command-discovery section · Updated: 2026-09-04 · Supersedes: committed internal-wheel hashes, split runtime roots, custom closure inference, vendored trees, shared common archives, and literal `Command(...)` discovery in `check_bundles.py`_
