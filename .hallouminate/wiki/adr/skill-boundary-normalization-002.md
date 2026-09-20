# ADR: Generous writer ingress ends before canonical persistence

Status: accepted (2026-08-24)

## Decision

<certain> Agent writer views may receive a closed set of syntax repairs, but semantic coercion and ambiguity reject. Any non-strict path emits a separate typed `NormalizationReceipt` bound to source and canonical digests.[^spec]

Canonical artifacts receive strict schema validation only. Persisted legacy artifacts enter through `contract migrate` and one exact schema/version adapter; `contract accept` never repairs them.

## Rationale

BAML demonstrates a useful separation: accept varied LLM-shaped text at ingress, rank or repair candidates under constraints, then validate the typed result. Easy Cheese adopts that separation without copying broad primitive coercions into durable artifact handling.[^research]

## Consequences

Receipts record action and field names, not raw values. Strict paths have no receipt. Zero or multiple candidates, unknown or missing semantic fields, inferred values, and fuzzy scalar coercion reject.

## Mold-to-Cook consequence (2026-09-17)

The phase handoff is a strict `MoldCookHandoff`, not a writer envelope. Its
artifact references are resolved and digest-checked by both Mold publication
and Cook acceptance. `MoldCookApproval` records the exact proposal and
response bytes; syntax normalization cannot create scope, plan, partial-plan,
or runner authority. Cook's non-ready preparation outcomes retain their
holds and requirements instead of being coerced into a runnable pointer.

[^spec]: `.cheese/specs/enforceable-skill-boundaries.md` sections Approach, Decisions, and Risks.
[^research]: `.cheese/research/baml-generous-input/baml-generous-input.md`; https://docs.boundaryml.com/guide/why-baml
