# ADR: Cheese ships a standard-library contract runtime

Status: accepted (2026-07-26)
Spec: [Cross-skill work contract](../specs/cross-skill-work-contract.md)

## Context

The original proposal used idiomatic YAML for persisted handoffs and WorkRecords, which required either ambient PyYAML or vendoring PyYAML into `cheese.pyz`. Vendoring created a distinct dependency and license path for one Easy Cheese bundle, while ambient PyYAML would break the Python-only install promise. Human-authored phase declarations still benefit from YAML readability.[^1]

## Decision

Persisted HandoffEnvelope and WorkRecord frontmatter is a JSON object parsed and rendered with Python's standard-library `json` module. Markdown remains the human-readable body format.

Source `skills/<phase>/references/handoff-contract.yaml` files remain YAML. Maintainers and CI install one exact pinned PyYAML version during bundle construction. The builder validates those source declarations and compiles them into a JSON-compatible global registry embedded in `skills/cheese/scripts/cheese.pyz`.

The released archive does not contain `yaml/`, a PyYAML license copy, or any runtime dependency on PyYAML. A `python3 -S` test loads the compiled registry and round-trips persisted JSON frontmatter.

`/cheese` remains the mandatory companion for contract-aware workflow skills because it owns shared work, handoff, and registry behavior. A missing companion fails with the exact instruction: `Cheese contract runtime is required; install easy-cheese's Cheese companion runtime`.

## Consequences

Repository authors retain readable YAML phase contracts. Released users receive one standard-library-only companion runtime, and Easy Cheese keeps one dependency policy across bundles. Build tooling must pin PyYAML and prove the released archive excludes it. The previous plan to ship vendored PyYAML and its license is rejected.

[^1]: `scripts/build_pyz.py:111-124`; `scripts/stage_release.py:1-10`; `scripts/install.sh:543-558`.