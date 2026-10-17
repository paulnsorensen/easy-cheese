# ADR: Agents write slim views and hosts normalize canonical contracts

Decision status: accepted
Spec: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/workflow-contract-milknado-seam.md`

## Context

<certain> Agents are the authors between most Easy Cheese phase calls. Invocation-known IDs, digests, versions, provenance, and coverage are computable by the host rather than semantic judgments.

Requiring those fields in agent output increases repair work and permits agents to contradict information the caller already owns.

## Decision

<certain> Persisted artifacts are canonical. Agents receive generated writer views and omit host-known or computed fields. A deterministic normalizer validates the writer view, rejects unknown or duplicate identity fields, and adds IDs, digests, versions, subject references, criterion IDs, coverage, derivation, and provenance.

<certain> Canonical ArtifactRef validates URI policy, SHA-256 digest, byte size, media type, and optional schema before a resolver exposes the slim `role/path/media_type` agent view.

<certain> New domain contracts use host-authored schema identity plus major/minor versions. Unsupported majors, future minors, and unknown fields reject before execution. Supported older minors validate against their registered schema and normalize forward.

<certain> JSON Schemas use Draft 2020-12 and are generated deterministically from frozen attrs/cattrs models through a project-owned generator. The new runtime adds no schema-generation dependency.[^1]

## Alternatives

- Agents author canonical artifacts: rejected because they would repeat computable facts.
- Rich self-contained requests: rejected because large diffs and logs belong behind validated artifact references.
- Version ranges or future-minor fail-open: rejected at the new trust boundary; legacy `compat.load` remains migration-only.[^2]

## Consequences

<certain> Canonical persistence stays auditable while agent prompts remain smaller. Conformance fixtures must cover first-pass validity, repair, output size, normalization, and version rejection.

[^1]: `skills/ultracook/references/pr-plan-schema.json:2`; `.cheese/research/attrs-schema-validator-generation/attrs-schema-validator-generation.md`.
[^2]: `src/easy_cheese_schemas/compat.py:158-175`.
