# ADR: Cross-skill execution starts from a canonical pointer

Status: accepted (2026-08-24)

## Decision

<certain> Durable phase handoffs publish a canonical JSON `HandoffPointer` last. It binds contract version, operation ID, request digest, source and destination phases, payload `ArtifactRef`, and an optional `NormalizationReceipt` reference.[^spec]

Producers validate payload and route before publication. Consumers validate the pointer, route, referenced bytes, receipt binding, and canonical payload before execution. Bare payloads do not execute.

Publication is idempotent by operation ID plus request digest. The same operation and request returns the existing pointer after full revalidation; a different request or corrupted reference rejects and is not overwritten.

## Consequences

The pointer is the phase boundary's commit record, not a universal continuity envelope. Mold → Cook is the first slice; later phases adopt the same gateway separately.

[^spec]: `.cheese/specs/enforceable-skill-boundaries.md` sections Approach, Decisions, and Interface sketches.
