# Skill Python bundle doctrine

Every skill that executes Python ships at most one same-named `.pyz` and invokes Python only through that archive. Runtime source is organized as importable packages under `src/`; checked-in skill directories contain deployment artifacts, not Python source.

Implementation began with Mold and Cook: their runtime now follows the package layout and closure gates below, while unmigrated skills retain transitional source layouts. The repository therefore still does not conform fully.

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

For migrated Mold runtime, package modules are authoritative. Files still required under `src/mold/` are thin compatibility entrypoints and are not copied into the Mold archive unless reachable. The generated document-rules projection lives only at `src/easy_cheese/skills/mold/_document_rules.py`.[^6]

Corpus path computation is authoritative in `src/easy_cheese/shared/paths.py`; `shared/scripts/paths.py` is a transitional delegator. Both package-layout and legacy bundles stage that producer rather than maintaining a second resolver.[^7]

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

Mold and Cook command modules use static imports. `minimal_closure` walks those imports, including transitional shared scripts, so command declarations and runtime closure have one ownership path. Post-closure duplicate Mold helpers are prohibited and tested absent.[^8]

Release staging calls the public layout-aware builder for Mold and Cook. The release test proves an isolated staged Mold-to-Cook contract round trip, not only command discovery.[^9]

Bundle currency checks materialize the selected worktree, index, or HEAD snapshot, reconstruct vendor dependencies from that snapshot, rebuild with the snapshot's build script, and compare the rebuilt archives with the selected tree. Live worktree source or vendor state cannot contaminate index/HEAD checks.[^10]

## Superseded topology

The shared `common.pyz` topology is removed. Mold and Cook now use `src/easy_cheese/skills/`, while unmigrated skills continue to use transitional `src/` and `shared/scripts/` sources; [[pyz-bundling-pipeline]] documents that remaining compatibility path.

[^1]: https://agentskills.io/specification#file-references
[^2]: https://packaging.python.org/en/latest/discussions/distribution-package-vs-import-package/
[^3]: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
[^4]: https://docs.python.org/3/library/zipimport.html
[^5]: https://docs.python.org/3/library/importlib.resources.html
[^6]: scripts/build_pyz.py:39-42
[^7]: src/easy_cheese/shared/paths.py:1-591
[^8]: src/easy_cheese/shared/bundles.py:82-132
[^9]: tests/python/test_stage_release.py:110-166
[^10]: scripts/check_bundles.py:55-190

_Source: human-approved repository doctrine and PR #478 cure · Updated: 2026-08-24 · Supersedes: split runtime roots and shared common bundle topology_
