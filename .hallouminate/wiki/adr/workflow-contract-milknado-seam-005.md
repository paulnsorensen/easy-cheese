# ADR: Payload schemas and transition routing remain separate

Decision status: accepted
Spec: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/workflow-contract-milknado-seam.md`

## Context

<certain> The earlier cross-skill contract proposed phase-owned YAML handoff contracts and a bundled runtime YAML parser.[^1] The approved payload design now has independent JSON Schemas, and existing artifact writers already know the source phase and next skill.[^2]

Repeating payload fields inside routing declarations would create two schema authorities.

## Decision

<certain> Domain JSON Schemas describe payloads only. PhaseContract references input and output schema URIs plus allowed destinations without restating payload fields.

<certain> Each skill authors a phase-local YAML declaration beside the skill. Build tooling validates and compiles all declarations into TransitionRegistry. Existing helper scripts load the compiled registry and have no runtime YAML dependency.

<certain> `write_artifact` uses its existing phase and next-skill inputs to validate the source, destination, and payload schema before persistence. A globally valid transition remains valid when an optional destination capability is absent; capability absence is a runtime result.

<certain> Existing `compat.load` and `parse_handoff_slug` signatures remain unchanged migration interfaces.

## Alternatives

- Put routing inside payload schemas: rejected because routing and domain data change for different reasons.
- Hard-code transitions in helpers: rejected because phase owners would not own their declarations.
- Load source YAML at runtime: rejected because the compiled registry is deterministic and sufficient.

## Consequences

<certain> This ADR supersedes the runtime-YAML requirement and `references/handoff-contract.yaml` declaration location in the older handoff ADRs. It does not rewrite or invalidate persisted legacy YAML artifacts.[^1]

[^1]: [Cross-skill handoff ADR](./cross-skill-work-contract-002.md); [bundled YAML runtime ADR](./cross-skill-work-contract-003.md).
[^2]: `shared/scripts/write_handoff_artifact.py:81-128`; `shared/scripts/handoff.py:71-116`.
