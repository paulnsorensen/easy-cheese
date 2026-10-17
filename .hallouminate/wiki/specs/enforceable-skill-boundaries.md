# Enforceable skill boundaries

<certain> The approved target is one enforceable Mold → Cook handoff slice plus doctrine-compliant bundle building. Canonical typed artifacts are validated at both producer and consumer boundaries; feature execution begins only from a ready `MoldCookHandoff` carried by a canonical `HandoffPointer`.[^spec]

## Boundary protocol

The public gateway is:

```text
Mold.finalize(spec, approval, planner_result?, plan?, mode) -> HandoffPointer
Cook.prepare(input, approvals, setup_evidence?) -> CookPreparationResult
Cook.accept(pointer: HandoffPointer) -> AcceptedArtifact
```

Publication writes and validates the canonical payload and optional
`NormalizationReceipt` before atomically revealing the pointer. Repeating the
same operation and request returns the fully revalidated result; reusing the
operation with a different request or corrupted referenced bytes rejects.[^spec]

## Preparation and authority

`CookPreparationResult` is a closed, non-executing outcome. Full mode requires
scope approval before planning and exact plan approval before a handoff;
unchanged approval is reused by digest, while detached or stale approval is
rejected. Light mode authorizes one curd without planner artifacts. Partial
approval carries its exact runnable subset and acknowledged remainder.

Runner setup is a separate approval. Its authorization is limited to named
paths and commands, and evidence must match the approved plan and authorization.
Missing or stale setup proof preserves the hold and does not permit feature
writes. Historical pointers are read only through the bounded migration path,
which verifies original integrity before asking for missing bindings.

## Acceptance zones

- Agent writer views are syntax-generous and semantics-strict.
- Canonical persistence and execution are strict.
- Persisted legacy artifacts use only exact schema/version adapters through `contract migrate`.
- `contract accept` accepts a pointer, never a bare payload.

The approved writer recovery set covers one uniquely identifiable candidate, comments, trailing commas, single quotes, unquoted object keys, uniquely implied closing delimiters, and declared writer shorthand. Missing semantic fields, unknown fields, fuzzy coercion, inferred values, and ambiguous repair reject.[^spec]

## Bundle target

Ownership derives from `src/easy_cheese/skills/<skill>`; shared runtime lives under `src/easy_cheese/shared`. Each Python-owning skill ships one same-named archive. Decorator-declared `@bundle_command` functions compile into that archive's dispatcher and generated command map.[^doctrine]

## Delivery order

The approved plan contains nine curds in seven dependency waves: independent #433 restack and #455 website extraction, canonical contracts, bundle runtime, command compilation, Mold publication, Cook acceptance, legacy migration/recovery, then snapshot and conformance gates.[^spec]

Cook → Press → Age → Cure and Wheypoint remain separate prepared follow-ups.

[^spec]: `.cheese/specs/enforceable-skill-boundaries.md`; `.cheese/plans/enforceable-skill-boundaries.curd-plan.json`.
[^doctrine]: [Skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md); https://github.com/paulnsorensen/easy-cheese/pull/472
