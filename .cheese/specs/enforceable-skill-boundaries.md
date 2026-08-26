---
slug: enforceable-skill-boundaries
status: approved
source: mold-handshake
created: 2026-08-24
confidence: high
gates_overridden: []
agent_introduced_scope:
  - HandoffPointer
  - NormalizationReceipt
  - AcceptedArtifact
  - PublishedArtifact
  - "@bundle_command"
  - contract migrate
  - contract accept
  - contract publish
entity_referent_bindings:
  - noun: ArtifactRef
    verdict: bound
    referent: src/easy_cheese_schemas/contracts.py:547-554
    citation: src/easy_cheese_schemas/contracts.py:547-554
    note: Existing immutable artifact identity contract.
  - noun: HandoffPointer
    verdict: new-entity
    referent: NEW ENTITY
    citation: approved dialogue
    note: Canonical pointer-last boundary commit record.
  - noun: NormalizationReceipt
    verdict: new-entity
    referent: NEW ENTITY
    citation: approved dialogue
    note: Typed evidence for non-strict normalization.
  - noun: bundle_command
    verdict: new-entity
    referent: NEW ENTITY
    citation: approved dialogue
    note: Decorator declaration compiled into each skill dispatcher.
gate_applicability:
  disposition: red-required
  work_class: behavior
  ui_surface: non-browser
---

# Enforceable skill boundaries and doctrine-compliant bundles

## Problem

Easy Cheese has canonical decorator-declared schemas and a compiled phase registry, but cross-skill artifacts are not uniformly validated at producer and consumer boundaries. Its current `common.pyz`, cross-skill source copying, flat runtime roots, and whole-package staging also conflict with the landed one-skill/one-bundle doctrine.

## Goals

- Enforce canonical typed artifacts between Mold and Cook.
- Validate payloads, routes, references, and normalization evidence before publication and execution.
- Move runtime ownership under `src/easy_cheese/skills/<skill>` and `src/easy_cheese/shared`.
- Ship one minimal, same-named, zip-safe archive per Python-owning skill.
- Preserve useful enforcement from open PRs without retaining superseded topology.

## Non-goals

- Schema ordinary utility command input and output.
- Retain or replace `common.pyz` with a central broker.
- Dual-write canonical and legacy artifacts.
- Apply heuristic or semantic coercion to persisted artifacts.
- Migrate Cook → Press → Age → Cure in the first replacement stack.
- Redesign Wheypoint or whole-work continuity.
- Merge the existing stale PR stack unchanged.
- Do nothing: that would leave unenforced boundaries and expand doctrine violations.


## Deferred follow-ups

- **enforceable-skill-boundaries-F001** — Extend the canonical gateway through Cook → Press → Age → Cure.
  - Destination: local_draft
  - State: prepared
  - Reference: `.cheese/issues/enforceable-skill-boundaries-001.md`
- **enforceable-skill-boundaries-F002** — Migrate Wheypoint as a separate boundary slice while preserving useful #430 projection and reference work.
  - Destination: local_draft
  - State: prepared
  - Reference: `.cheese/issues/enforceable-skill-boundaries-002.md`

## Approach

Deliver one vertical Mold → Cook boundary. Package ownership derives from `src/easy_cheese/skills/<skill>`; `@bundle_command` declarations compile into the owning archive dispatcher and generated command guidance. Decorator models remain payload-schema authority, while `phase-contract.yaml` remains route authority.

Agent writer views pass through a syntax-generous, semantics-strict normalizer. Persisted legacy inputs use only exact schema/version adapters through `contract migrate`. Publication prepares the canonical payload and any required `NormalizationReceipt`, then reveals a canonical `HandoffPointer` last. Consumers execute only after `contract accept` validates the pointer, route, references, receipt binding, and canonical payload.

## Decisions

- Use clean replacement PRs and close stale shells only after preserved behavior exists.
- Derive bundle ownership and archive name from package layout; add no runtime manifest.
- Compile decorator-declared commands into generated dispatchers and guidance.
- Validate at both producer and consumer boundaries.
- Apply bounded syntax repair only to agent writer views; legacy artifacts use deterministic adapters.
- Persist a separate typed normalization receipt only when a non-strict path is used.
- Execute only through canonical handoff pointers; migrate legacy handoffs explicitly.
- Publish payload and receipt before atomically revealing the pointer.
- Bind idempotency to operation ID, request digest, and canonical digest.
- Declare adapter sunset metadata when each adapter is introduced.
- First delivery ends at Mold → Cook plus closure, isolation, and currency enforcement.
- Minor decisions: record field names but never raw values in receipts; require legacy receipt source schema/version; preserve current strict canonical-version equality.

## Acceptance

- AC-1: WHEN the bundle builder discovers a Python-owning skill THE SYSTEM SHALL derive exactly one same-named archive and a decorator-compiled command surface from its package.
- AC-2: WHEN phase contracts compile THE SYSTEM SHALL reject missing schemas, incompatible destination inputs, duplicate commands, unreferenced commands, and generated projection drift.
- AC-3: WHEN Mold receives imperfect agent writer output THE SYSTEM SHALL apply only the approved syntax recovery actions, reject ambiguous or semantic repair, and bind any normalization receipt to source and canonical digests.
- AC-4: WHEN a producer publishes a handoff THE SYSTEM SHALL validate payload and route, prepare immutable payload and receipt files, and reveal one idempotent canonical pointer last.
- AC-5: WHEN a legacy handoff is migrated THE SYSTEM SHALL require a provable route and exact supported source version, emit a receipt, publish a canonical pointer, and enforce the adapter sunset contract.
- AC-6: WHEN Cook receives Mold work THE SYSTEM SHALL reject bare payloads and execute only after validating the canonical pointer, route, references, receipt, and CurdPlan.
- AC-7: WHEN a skill archive is built or executed THE SYSTEM SHALL reject unresolved deferred imports, native members, ambient dependencies, repository-path dependence, and cross-skill archive calls.
- AC-8: WHEN replacement-stack conformance runs THE SYSTEM SHALL rebuild from the correct index or HEAD snapshot, preserve selected assertions and recent schema behavior, and prove all bundle interfaces in isolation before stale PR shells close.

## Test Contracts

| Acceptance ID | Interface referent | Outermost stable seam | Expected failure | Mode | Interface version | Matrix rows |
| --- | --- | --- | --- | --- | --- | --- |
| AC-1 | `scripts/build_pyz.py` | bundle build plus own-archive subprocess | On current main, the assertion fails because ownership still depends on central registries and extra archives. | tracer | | |
| AC-2 | phase/schema/command compilers | generated-registry build gate | A mismatched destination schema or duplicate command currently lacks the unified rejection gate. | tracer | | |
| AC-3 | Mold `contract publish` | isolated `mold.pyz` subprocess | Current Mold has no closed syntax-recovery and receipt-binding boundary. | tracer | | |
| AC-4 | shared publication gateway | filesystem crash/retry integration test | Current publication cannot prove payload-plus-receipt pointer-last atomicity and operation conflict behavior. | tracer | | |
| AC-5 | `contract migrate` | isolated migration subprocess | Current runtime has no exact-version migration-only path with declared sunset enforcement. | tracer | | |
| AC-6 | Cook `contract accept` | isolated Mold-pointer-to-Cook execution | Current Cook can validate payloads but does not require a route-bound HandoffPointer before execution. | tracer | | |
| AC-7 | bundle closure gate | archive inspection plus isolated subprocess | Current closure permits superseded whole trees and lacks complete native and ambient-runtime rejection. | tracer | | |
| AC-8 | bundle currency/conformance gate | staged-index and CI-HEAD reconstruction | Current local currency checking does not enforce the complete doctrine-native snapshot and boundary contract. | tracer | | |

## Interface sketches

```pseudocode
@bundle_command(name: str)
def command(argv: Sequence[str]) -> int

migrate(
    legacy_handoff: LegacyHandoff,
    operation_id: OperationId,
) -> PublishedArtifact

accept(
    pointer: HandoffPointer,
) -> AcceptedArtifact

publish(
    writer_view: AgentWriterView,
    invocation: InvocationContext,
    destination: Phase,
    operation_id: OperationId,
) -> PublishedArtifact

HandoffPointer {
    contract_version: ContractVersion
    operation_id: OperationId
    request_digest: Sha256
    source_phase: Phase
    destination_phase: Phase
    payload: ArtifactRef
    normalization_receipt: ArtifactRef | null
}

NormalizationReceipt {
    ingress_kind: writer_view | legacy_artifact
    source_schema_uri: Uri | null
    source_version: ContractVersion | null
    normalizer_id: str
    actions: tuple[NormalizationAction, ...]
    source_digest: Sha256
    canonical_digest: Sha256
}

AcceptedArtifact {
    canonical: CanonicalArtifact
    normalization_receipt: ArtifactRef | null
}

PublishedArtifact {
    pointer: HandoffPointer
    canonical: CanonicalArtifact
    normalization_receipt: ArtifactRef | null
}
```

## Risks

- Syntax recovery could change intent; the closed action set, unique-candidate rule, and canonical validation bound it.
- Pointer-last publication could leave prepared files after interruption; recovery must revalidate them before revealing or rejecting the pointer.
- Compatibility adapters could become permanent; every adapter declares `remove_after` and removal gates.
- Bundle closure inference could miss dynamic imports; isolated interface execution complements static analysis.
- Conflict resolution could restore superseded topology; doctrine-specific conformance tests reject it.

## Open questions

- None.

## Quality gates

- `python3 skills/cook/scripts/cook.pyz validate <planner-view> --schema agent-writer-view`: typed planner writer view conforms.
- Host normalization of the planner view: nine-curd CurdPlan materializes with matching digest.
- Focused RED tracers for every acceptance criterion: each fails on current main for the named witness.
- `just check`: all repository checks pass cumulatively for every curd.
- Bundle-only subprocess suite: every shipped interface passes without repository paths, `PYTHONPATH`, or ambient site packages.

## Curds

Validated plan: **9 curds / 7 dependency waves**.

1. Wave 1: restack #433; extract #455 website relocation; define canonical handoff contracts.
2. Wave 2: migrate doctrine-compliant bundle runtime and closure.
3. Wave 3: compile `@bundle_command` dispatchers and generated command guidance.
4. Wave 4: make Mold the canonical pointer-last producer.
5. Wave 5: make Cook the pointer-only consumer.
6. Wave 6: add exact legacy migration, adapter sunsets, and interrupted-publication recovery.
7. Wave 7: enforce snapshot currency and full conformance, then close replaced PR shells.

Planner writer-view SHA-256: `40499f8cc4da9d556d544f040d6e1e24f0c2b67775ae427935f29b37c87f40d7`.
Canonical plan digest: `sha256:14974067a69eda4cfa12edd56ea753a4af7edd4e82d5614edef3fd048fa7597d`.

## References

[^bundle-doctrine]: [PR #472](https://github.com/paulnsorensen/easy-cheese/pull/472).
[^canonical-contracts]: [PR #395](https://github.com/paulnsorensen/easy-cheese/pull/395).
[^spec-enforcement]: [PR #466](https://github.com/paulnsorensen/easy-cheese/pull/466).
[^writer-normalization]: [PR #467](https://github.com/paulnsorensen/easy-cheese/pull/467).
[^generated-guidance]: [PR #468](https://github.com/paulnsorensen/easy-cheese/pull/468).
[^baml]: [BoundaryML Why BAML?](https://docs.boundaryml.com/guide/why-baml).
