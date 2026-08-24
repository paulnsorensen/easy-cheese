# Skill Python bundle doctrine

Every skill that executes Python ships at most one same-named `.pyz` and invokes Python only through that archive. Runtime source is organized as importable packages under `src/`; checked-in skill directories contain deployment artifacts, not Python source.

This doctrine was approved on 2026-08-24. The repository does not yet conform fully; enforcement and migration belong to follow-up work rather than the doctrine-only change that introduced these rules.

## Skill deployment contract

- A skill that executes Python ships exactly `skills/<skill>/scripts/<skill>.pyz`.
- A skill that does not execute Python ships no `.pyz`.
- Skill instructions and references invoke only their own bundled archive. They never invoke `src/**/*.py`, repository automation, loose Python helpers, `common.pyz`, or another skill's archive.
- Skill-root-relative paths are the portable reference form required by the Agent Skills file-reference convention.[^1]
- Python source never lives under `skills/`. Checked-in `.pyz` files are generated deployment artifacts, never source of truth.
- Non-executable references and assets remain ordinary skill resources; “bundle-only” applies to executable Python, not Markdown, schemas, templates, or other documentation.

## Source layout

Runtime Python has two import packages:

```text
src/
├── easy_cheese/
│   ├── shared/
│   └── skills/
│       └── <python_skill_name>/
└── easy_cheese_schemas/
```

- `easy_cheese_schemas` is the independently published PyPI package.
- `easy_cheese` is repository-internal and must be excluded from the PyPI distribution.
- Skill slugs remain kebab-case in `skills/`; import-package segments use underscores because Python import packages should be valid identifiers.[^2]
- Shared runtime helpers live in `src/easy_cheese/shared/`.
- Skill-owned runtime code lives in `src/easy_cheese/skills/<python_skill_name>/`.
- Tests remain under `tests/`.
- Repository build, release, generation, and maintenance programs may live under `scripts/`. Runtime Python has no other source root.

The `src` layout separates importable code from repository files and prevents accidental imports from the working directory.[^3]

## Zip-safe runtime

A skill archive may contain Python modules, bytecode, and immutable package resources. Bundled dependencies must be pure Python and zip-importable.

The following are prohibited:

- native extension modules such as `.so` and `.pyd`;
- platform-specific libraries such as bundled `.dll` or `.dylib` files;
- required external executables;
- runtime package installation or downloads;
- mandatory extraction before the skill can run.

Python's ZIP importer supports `.py` and `.pyc` modules but explicitly rejects dynamic extension modules.[^4] Package resources may be read from ZIP archives through `importlib.resources`, so non-Python immutable data is allowed when it is part of the reachable runtime closure.[^5]

## Minimal bundles

Minimal means both few artifacts and narrow contents:

1. At most one same-named `.pyz` per skill.
2. Only that skill's entrypoints and transitive runtime closure.
3. Only required shared and schema modules.
4. Only approved pure-Python third-party dependencies.
5. No whole-package or whole-tree inclusion without explicit justification.

The build must eventually enforce dependency closure, reject native artifacts, verify bundle currency, and execute every bundled interface with repository paths, `PYTHONPATH`, and ambient site packages unavailable. Those gates are follow-up implementation work; this page establishes their target contract.

## Superseded topology

This doctrine supersedes the current split between `src/` and `shared/scripts/`, the multi-consumer `common.pyz`, cross-skill archive calls, and retained runtime ownership under the retired `ultracook` skill. Until migration lands, [[pyz-bundling-pipeline]] documents current behavior while this page defines the target.

[^1]: https://agentskills.io/specification#file-references
[^2]: https://packaging.python.org/en/latest/discussions/distribution-package-vs-import-package/
[^3]: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
[^4]: https://docs.python.org/3/library/zipimport.html
[^5]: https://docs.python.org/3/library/importlib.resources.html

_Source: human-approved repository doctrine · Updated: 2026-08-24 · Supersedes: split runtime roots and shared common bundle topology_
