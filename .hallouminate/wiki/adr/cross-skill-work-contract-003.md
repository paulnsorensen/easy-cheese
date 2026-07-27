# ADR: Cheese bundles its YAML contract runtime

Status: accepted; amended 2026-07-27
Spec: [Cross-skill work contract](../specs/cross-skill-work-contract.md)

## Context

The original proposal used idiomatic YAML for persisted handoffs and WorkRecords. A 2026-07-26 amendment changed those documents to JSON because bundling PyYAML was treated as a separate user dependency and release policy. Python's `zipapp` documentation resolves that concern: build tooling can install application dependencies into the archive source directory, after which users receive one file and need only a compatible Python interpreter.[^1]

Zip applications cannot load native extension modules directly. PyYAML's Python modules can run without its optional C extension, so the archive must include only the pure-Python `yaml` package and exclude `.so` and `.pyd` files.[^2]

## Decision

Persisted HandoffEnvelope and WorkRecord frontmatter is YAML parsed with `yaml.safe_load` and rendered deterministically with `yaml.safe_dump`. The `---` fences and Markdown bodies remain unchanged. CLI requests and responses remain JSON.

Source `skills/<phase>/references/handoff-contract.yaml` files also remain YAML. Maintainers and CI install one exact pinned PyYAML version during bundle construction. The builder validates those source declarations, embeds the compiled registry, and copies PyYAML's pure-Python package plus its license into `skills/cheese/scripts/cheese.pyz`.

The released archive contains no native extension, bytecode cache, or package metadata. Tests execute the archive under `python3 -S` and prove registry loading plus YAML HandoffEnvelope and WorkRecord round trips without ambient site packages.

`/cheese` remains the mandatory companion for contract-aware workflow skills because it owns shared work, handoff, and registry behavior. A missing companion fails with the exact instruction: `Cheese contract runtime is required; install easy-cheese's Cheese companion runtime`.

## Consequences

Released users install neither PyYAML nor any other Python library separately; they receive one self-contained `cheese.pyz` and provide only a compatible Python interpreter. The archive is larger and carries PyYAML's license, but repository-authored contracts and persisted human-readable state share one YAML representation and one pinned parser implementation.

[^1]: [Python `zipapp`: Creating Standalone Applications](https://docs.python.org/3/library/zipapp.html#creating-standalone-applications-with-zipapp).
[^2]: [Python `zipapp`: Caveats](https://docs.python.org/3/library/zipapp.html#caveats).