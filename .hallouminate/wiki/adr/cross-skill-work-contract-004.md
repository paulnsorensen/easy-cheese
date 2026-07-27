# ADR: Frozen dataclasses with cattrs define work-contract models

Status: accepted 2026-07-27
Spec: [Cross-skill work contract](../specs/cross-skill-work-contract.md)

## Context

The handoff runtime receives untrusted YAML mappings but its business logic needs named, immutable records. Manual `from_mapping` and `as_mapping` methods duplicated field lists, while the compiled registry remained nested dictionaries whose string keys obscured the `PayloadSchema`, `PhaseContract`, and `TransitionRegistry` concepts.[^1]

Two model styles fit the runtime: frozen standard-library dataclasses with cattrs, or attrs classes with cattrs. cattrs supports both. Its default primitive hooks coerce values and its generated class hooks ignore unknown keys unless configured otherwise, so an unconfigured converter is not a valid boundary for contract data.[^2]

## Decision

Use frozen standard-library dataclasses for `HandoffEnvelope`, `PayloadSchema`, `PhaseContract`, and `TransitionRegistry`, and use one cached cattrs converter to structure and unstructure them. Configure the converter to reject unknown fields and register strict primitive hooks so values such as `phase: 1` or `payload: []` fail instead of being coerced.[^3]

Keep lifecycle, transition, and dynamic payload-schema rules explicit in the domain functions. cattrs owns mapping-to-model conversion; it does not replace business validation. Use attrs models only when a concrete attrs converter or validator removes more code than it introduces.

Pin cattrs and its runtime dependencies exactly in maintainer and CI environments. At this decision the versions are cattrs 26.1.0, attrs 26.1.0, and typing-extensions 4.16.0. cattrs 26.1.0 declares attrs and typing-extensions as runtime dependencies, and all three publish platform-independent Python wheels.[^4]

The release-packaging layer must bundle these packages and their licenses with PyYAML inside `cheese.pyz`; released users still install no Python libraries separately.

## Consequences

Boundary parsing now validates once and returns typed records. Registry consumers use attributes rather than nested string keys, and frozen records prevent field reassignment while preserving ordinary dictionaries for phase-owned payloads.

The dependency set grows by three pure-Python distributions. Bundle construction, archive inspection, license checks, and `python3 -S` tests must cover the complete pinned set. Any new converter configuration must preserve strict non-coercing input behavior.

[^1]: `shared/scripts/handoff.py:187-238,307-469`
[^2]: [cattrs 26.1.0 default hooks](https://github.com/python-attrs/cattrs/blob/v26.1.0/docs/defaulthooks.md) and [generated hook configuration](https://github.com/python-attrs/cattrs/blob/v26.1.0/docs/customizing.md)
[^3]: `shared/scripts/handoff.py:171-217`; `tests/shared/python/test_handoff.py:45-54`
[^4]: [cattrs 26.1.0 dependency metadata](https://github.com/python-attrs/cattrs/blob/v26.1.0/pyproject.toml#L653-L675), [cattrs files](https://pypi.org/project/cattrs/26.1.0/#files), [attrs files](https://pypi.org/project/attrs/26.1.0/#files), and [typing-extensions files](https://pypi.org/project/typing-extensions/4.16.0/#files)
