## Handoff slug

```text
status: gated: confirm pre-terminal crash recovery, then finish the remaining protocol schemas before curdling
next: mold
mode: single
artifact: .cheese/notes/root-cheese-milknado-decision-audit.md
git: main@3a53fc9
created: 2026-07-29T08:58:33Z
parents: [global-fanout-policy]
<certain> Identity, WorkAttempt, immutable plan/curd lineage, and WorkRecord compaction authority are mostly locked; resume `/mold` by confirming the user's leaning toward terminalizing a lost invocation before recovery, then close the remaining protocol forks listed below.
```

## Document

## Goal

- <certain> Define the complete agentic protocol for Easy Cheese alone and Easy Cheese accelerated by Milknado.
- <certain> Keep Easy Cheese semantic contracts harness-agnostic while giving Milknado explicit import, execution, checkpoint, recovery, and result-adapter contracts.
- <certain> Finish with two coupled implementation specs, one for Easy Cheese and one for Milknado, plus one shared compatibility and conformance-fixture matrix.
- <certain> Include planner, review, operation, continuation, WorkRecord, `$wheypoint`, artifact, and adapter schemas rather than designing only the happy-path curd handoff.

## State

- <certain> This is an advanced `/mold` dialogue, not an approved implementation spec.
- <certain> The current decisions were adversarially audited in `.cheese/notes/root-cheese-milknado-decision-audit.md`; decisions made after that audit are recorded below.
- <certain> External protocol, SDK, validation, and retry-identity research is captured in the durable reports listed under Artifacts.
- <certain> No tracked source code was changed by this dialogue or checkpoint.
- <certain> Easy Cheese is `main@3a53fc9`, tracking `origin/main`, with only untracked `.claude/` observed after the gate run.
- <certain> Milknado is `main@c7c1cf9`, tracking `origin/main`, with only untracked `.serena/` observed.
- <certain> PR #331 contains an unmerged cross-skill contract; treat it as evidence and a migration constraint, not current authority.
- <certain> PR #358, earlier ADRs, and the prior WorkRecord/Handoff model are evidence to audit, not automatically ratified decisions.
- <certain> `just check` passes after repairing ignored local Markdown heading and virtual-environment permission drift; neither repair changes tracked repository content.

## Locked decisions

### Ownership and boundaries

- <certain> Easy Cheese owns `CurdPlan`, `CurdResult`, semantic planning, review, operation, WorkRecord, compaction, and continuation contracts.
- <certain> Milknado owns curd import, graph mapping, graph persistence, physical scheduling, and actual executor resolution.
- <certain> Root `$cheese` owns policy and orchestration intent; the selected executor owns runtime state.
- <certain> Easy Cheese and Milknado-assisted operation are both first-class modes.
- <certain> Two ingress paths remain required:
  1. raw goal or spec to semantic planning, physical planning, batching, and graph construction;
  2. approved `CurdPlan` to direct Milknado import, bypassing semantic decomposition and cross-curd batching.
- <certain> `curd`, `change`, `batch`, `wave`, `node`, `operation`, `invocation`, and `agent` are distinct concepts.
- <certain> At the adapter seam, one curd maps to one Milknado goal/task group with curd-level aggregate verification.
- <certain> Milknado `GOAL` is runtime graph state and does not belong in `CurdPlan`.
- <certain> There is no universal curd, wave, or node count cap.
- <certain> Human configuration outranks an agent request, which outranks executor defaults; the resolved execution choice is recorded.
- <certain> A human gate uses projected cost including retries, reviews, remediation, checkpoints, and runtime capacity.

### Planning and review

- <certain> Semantic planning and physical execution planning are separate stages.
- <certain> The semantic planner consumes `PlannerRequest` and produces `PlannerResult`, which may contain a `CurdPlan`.
- <certain> Planner intent covers at least `decompose`, `remediate`, and `replan`.
- <certain> Planner evidence covers at least `spec`, `review_result`, `curd_result`, `diagnosis`, and `repository_context`.
- <certain> Standalone Easy Cheese may use a pure agent followed by deterministic validation.
- <certain> Milknado may add deterministic grouping and deduplication, use an agent only for ambiguity, and validate the same semantic result.
- <certain> A clean review batch produces `no_work`, not an empty remediation plan or review-specific short-circuit flag.
- <certain> Direct finding-to-curd routing is rejected; review findings enter `PlannerRequest(intent=remediate)`.
- <certain> Taste-test and `/age` are review types in one typed family.
- <certain> Review consumes batches and preserves successful items when another item fails.
- <certain> Batch item correlation never relies on array position.

### Operation and invocation identity

- <certain> The generic protocol is `OperationInvocation<TRequest> -> OperationCheckpoint<TResult>* -> OperationOutcome<TResult>`.
- <certain> `Operation` is the correct term because execution may use an agent, deterministic code, or a workflow.
- <certain> `operation_id` identifies one immutable semantic request contract.
- <certain> `invocation_id` identifies one admitted execution of that operation.
- <certain> Transport replay and Milknado-internal transient retries remain inside one invocation until exactly one terminal outcome closes it.
- <certain> A post-terminal retry receives a new invocation under the same operation.
- <certain> A semantic change to goal, subject, intent, or acceptance contract creates a new operation.
- <certain> Changing executor strategy, model, limits, runtime environment, or retry creates a new invocation without changing the operation.
- <certain> Operation execution status and domain result status are separate dimensions.
- <certain> A failed, cancelled, timed-out, or interrupted operation may still carry a valid partial domain result.
- <certain> Domain result types own their partial-completion ledgers.
- <certain> Checkpoints are append-only and the terminal outcome is self-contained.

### WorkRecord and WorkAttempt

- <certain> `WorkRecord` is the living continuity authority for one user work item.
- <certain> `WorkAttempt` is a first-class, independently resumable orchestration lineage under one WorkRecord.
- <certain> WorkAttempt identity is independent of branch, worktree, harness, remote worker, executor, and Milknado graph.
- <certain> A WorkAttempt owns tentative context and groups multiple operations across phases and environments.
- <certain> WorkRecord creation atomically creates its initial WorkAttempt.
- <certain> Additional WorkAttempts require an explicit `fork_attempt` action with rationale and parent attempt references.
- <certain> Replanning, phase changes, retries, model changes, and environment moves remain inside the same WorkAttempt.
- <certain> Converging approaches creates a new WorkAttempt referencing all parent attempts; historical attempts are not merged or rewritten.
- <certain> Accepted shared context belongs to WorkRecord; attempt-local context remains tentative until explicitly promoted.

### Plan and curd identity

- <certain> Every successful planning operation produces a new immutable `CurdPlan` with a new `plan_id` and canonical digest.
- <certain> Replanning creates a new plan and references prior plans by stable ID plus digest; it never mutates an earlier plan.
- <certain> An unchanged curd retains the same `curd_id + digest` when referenced by multiple plans.
- <certain> A semantic change to curd goal, scope, inputs, outputs, or acceptance contract creates a new `curd_id` with explicit derivation from its predecessor.
- <certain> Physical placement, wave, batch, node, executor, and model changes do not change curd identity.
- <certain> Easy Cheese mints Easy Cheese work, attempt, operation, invocation, plan, curd, compaction, and continuation identities.
- <certain> Milknado mints Milknado identities and never invents a value in the Easy Cheese namespace.
- <certain> Milknado goal, task, graph, node, run, and executor-attempt IDs remain foreign runtime provenance.

### WorkRecord compaction and `$wheypoint`

- <certain> `$wheypoint` is a workflow-compaction operation over WorkRecord, not a second durable authority.
- <certain> A compaction atomically updates the living WorkRecord and emits an immutable `CompactionRecord` receipt.
- <certain> A cold-reader Wheypoint note is a projection of WorkRecord and CompactionRecord state.
- <certain> Repeated compactions retain stable work and attempt identity while receiving new compaction identities.
- <certain> `OperationCheckpoint` and WorkRecord compaction solve different problems and remain separate.
- <certain> Session, Git, harness, model, and creation time are provenance, not identity.
- <certain> `$wheypoint --split` explicitly forks child WorkAttempts with parent attempt and compaction references.
- <certain> Joining attempts inside one WorkRecord creates a convergence WorkAttempt; unresolved conflicts remain gated.
- <speculative> Joining different WorkRecords should require an explicit new authority decision rather than silently merging identities.

### Agent-facing compaction helper

- <certain> The helper contract is the single-shot semantic-delta model named A2 in the dialogue.
- <certain> Ordinary managed agents perform one checkpoint call; `OperationInvocation` supplies the continuity reference automatically.
- <certain> Standalone `$wheypoint` may use `--current` only when current work and attempt resolution is deterministic.
- <certain> A read-only `prepare` or inspection path is optional and reserved for ambiguity, conflict, stale state, joins, or explicit mutation of existing structured entries.
- <certain> Agents submit orientation, compact narrative, new decisions or questions, artifact references, explicit resolutions, and desired continuation.
- <certain> The runtime owns IDs, revisions, parentage, paths, canonical digests, provenance capture, carry-forward, preservation ledger, atomic persistence, and replay handling.
- <certain> Omitted protected state is carried forward; omission never means deletion.
- <certain> Generic deletion is absent from the agent contract; closure uses explicit verbs such as resolve, park, supersede, unlink, or abandon.
- <certain> The full Pydantic `CompactionRecord` is runtime output and fixture material, not an agent-authored input.
- <certain> Ambiguity or conflict produces a structured no-write error rather than prose that agents must parse.

### Continuation

- <certain> Outcome evidence does not request or select the next phase by default.
- <certain> `ContinuationAssessment` carries at least `complete`, `blocked`, `choice_required`, or `continuable`, plus unranked candidates with origin and rationale.
- <certain> `preferred` is null unless explicit intent or authorized deterministic policy supports a choice.
- <certain> Agents may add unranked candidates; the phase registry validates them; agents do not rank or silently select phases.
- <certain> `ContinuationDecision` records a selected phase, hold, or null, with basis `explicit_user`, `authorized_policy`, or `deterministic_singleton`.
- <certain> Applying a continuation decision and its WorkRecord revision is atomic.
- <certain> Multiple valid transitions without user intent produce choices without preselection.
- <certain> `gated` is a valid continuation state and not an execution failure.
- <certain> The old dual-purpose Handoff concept is split into evidence, assessment, decision, and applied record, although exact type boundaries remain open.

### Canonical schema and validation substrate

- <certain> Pydantic v2 models are the canonical build-time schema source.
- <certain> Generated JSON Schema Draft 2020-12 is the interchange schema.
- <certain> Agent requests, agent results, protocol envelopes, and conformance fixtures use JSON by default.
- <certain> YAML and frontmatter remain discovery or human-configuration syntax where explicitly retained; schemas and fixtures do not live in frontmatter.
- <certain> `cheese.pyz` strictly decodes bounded UTF-8 JSON, rejects duplicate keys and non-finite numbers, and validates every trust-boundary payload.
- <certain> Runtime model validation uses generated model-specific pure-Python validators rather than bundling Pydantic or a generic JSON Schema engine.
- <certain> Build-time parity tests prove Pydantic and generated validators accept and reject the same fixtures.
- <certain> No Draft 7 down-conversion is required for the selected Python path.

### Delivery shape

- <certain> Produce two coupled specs and one shared compatibility and fixture matrix, not one blended monolith.
- <certain> Define models, generated schemas, fixtures, identity rules, error rules, and generated validators before wiring orchestration.
- <certain> Both repositories implement producer and consumer behavior against the same fixture matrix.
- <certain> Milknado then implements curd import, graph mapping, checkpoint and outcome production, and result adaptation.
- <certain> Easy Cheese then wires root orchestration, review-to-planner flow, WorkRecord compaction, and continuation handling.
- <certain> Earlier ADRs, PR #331, and PR #358 must be retained, amended, or superseded explicitly.

## Immediate pending decision

- <speculative> The user currently leans toward pre-terminal crash recovery option A but has not ratified it.
- <speculative> Under option A, a coordinator first proves that the old executor is revoked or fenced, terminalizes the lost invocation, then admits a new invocation under the same operation with a validated `resume_from` checkpoint reference.
- <speculative> If the coordinator cannot prove exclusive ownership, the old invocation remains indeterminate and recovery does not start.
- <certain> Resume `/mold` by confirming, revising, or rejecting this option before moving to the other forks.

## Remaining forks before spec approval

### Checkpoint, crash, and recovery protocol

1. <don't know> Confirm option A for pre-terminal crash recovery versus same-invocation fenced epochs or operation-specific recovery policy.
2. <don't know> Define executor ownership proof, lease expiry, revocation, fencing tokens, and the exact indeterminate state when ownership cannot be proven.
3. <don't know> Define terminal execution statuses and reason codes for interrupted, lost, timed-out, cancelled, failed, and rejected invocations.
4. <don't know> Define `resume_from` fields, checkpoint eligibility, and whether a new invocation may resume only the immediately preceding invocation or any compatible checkpoint under the operation.
5. <don't know> Decide whether every checkpoint carries a full valid domain partial snapshot, a delta, or both; specify reconstruction and validation rules.
6. <don't know> Define sequence origin, monotonicity, gap handling, out-of-order delivery, and concurrent checkpoint rejection.
7. <don't know> Define duplicate checkpoint replay by sequence and digest, plus conflict behavior for reused sequence with changed content.
8. <don't know> Define checkpoint and outcome replay after terminalization, including duplicate terminal outcomes and late writes from fenced executors.
9. <don't know> Bound checkpoint input size, frequency, retention, storage growth, and projected-cost accounting.
10. <don't know> Define crash recovery for the WorkRecord and CompactionRecord transaction itself, including prepared state, promotion order, reconciliation, and idempotent retry.

### Remaining identity and provenance graph

11. <don't know> Define WorkAttempt lifecycle fields and distinguish stored control state from progress derived from operations and continuation records.
12. <don't know> Define when a changed user objective stays inside one WorkRecord versus creating a new WorkRecord.
13. <don't know> Define stable review request and review-result item identity for batch correlation and partial failure.
14. <don't know> Define identities and reference lifetimes for `ContinuationAssessment`, `ContinuationDecision`, and the applied continuation transaction.
15. <don't know> Define exact `CompactionRecord` identity, parent-compaction references, and work-scoped versus attempt-scoped compaction rules.
16. <don't know> Define artifact identity independently from path, including whether every artifact receives an Easy Cheese `artifact_id` in addition to its digest.
17. <don't know> Define foreign runtime references with issuer namespace, subsystem, project or database scope, graph, goal, task, node, run, and executor-attempt fields.
18. <don't know> Decide when a handoff artifact may reuse the producing invocation's `operation_id` and when it requires a separate artifact-producing operation with an explicit relation.

### WorkRecord, compaction, and continuation schemas

19. <don't know> Draft exact WorkRecord and WorkAttempt fields, bounded context sections, revision rules, and accepted-versus-tentative promotion operations.
20. <don't know> Draft exact `CompactionDraft`, `CompactionRecord`, preservation ledger, and cold-reader projection schemas.
21. <don't know> Specify the A2 CLI and JSON request fields, managed continuity-reference injection, standalone `--current` resolution, optional prepare flow, and structured error codes.
22. <don't know> Define stable IDs for decisions, questions, blockers, and artifact links so compaction can prove carry-forward, resolution, parking, or supersession.
23. <don't know> Define concurrent compaction behavior, stale snapshot handling, canonical request fingerprints, replay lookup, and lost-response recovery.
24. <don't know> Define exact same-WorkRecord split and join transactions, conflict presentation, and convergence-attempt creation.
25. <don't know> Decide cross-WorkRecord join behavior: reject, create a new WorkRecord, or explicitly select one authority while preserving the other as evidence.
26. <don't know> Decide whether raw transcripts are retained, referenced by harness-local provenance, content-digested, redacted, or deliberately excluded.
27. <don't know> Bound CompactionRecord history and define archival or garbage-collection policy without breaking lineage or auditability.
28. <don't know> Choose persisted instance representation for WorkRecord, CompactionRecord, continuation records, and human projections; JSON interchange is locked, but persisted JSON, YAML, and Markdown projection roles remain open.
29. <don't know> Finish the split between immutable handoff evidence, continuation assessment, human or policy decision, and applied WorkRecord transition; settle exact names and references.
30. <don't know> Define assessment staleness, candidate schema, registry validation, preferred-choice rules, decision basis fields, application conflicts, and `gated` projection.

### Artifact and result ownership

31. <don't know> Confirm whether semantic deliverables and evidence belong only in domain results while runtime diagnostics, usage, executor provenance, and logs belong only in `OperationOutcome`.
32. <don't know> Draft the artifact reference schema, including ID, digest algorithm, digest, media type, role, producer, size, URI or path, availability, and redaction metadata.
33. <don't know> Decide whether stored artifacts repeat their own path, derive it from identity, or support relocation through an external reference without self-path fields.
34. <don't know> Define artifact behavior in valid partial results, failed invocations, checkpoint snapshots, retries, and result aggregation.
35. <don't know> Define artifact trust-boundary checks for path normalization, digest verification, bounded reads, missing content, and mutable external URLs.

### Planner, review, and CurdResult schemas

36. <don't know> Draft exact `PlannerRequest` fields, typed evidence unions, intent-specific invariants, and subject references.
37. <don't know> Define `PlannerResult` outcomes and valid-partial dispositions without conflating executor failure with domain completeness.
38. <don't know> Draft `ReviewRequest` and `ReviewResult` types, taste-test and `/age` discriminators, batch-item correlation, and item-level partial failure.
39. <don't know> Draft `CurdResult` fields for acceptance criteria, completed and missed work, semantic artifacts, evidence, follow-ups, and foreign runtime provenance.
40. <don't know> Define the canonical semantic curd digest fields and normalization rules that determine whether curd identity survives replanning.
41. <don't know> Choose deterministic interim behavior when a curd is physically too large and no curd-local splitter is configured: reject, execute whole under an explicit capability, or another bounded behavior.

### Milknado adapter contract

42. <don't know> Draft exact raw-goal ingress and approved-`CurdPlan` import requests, results, and trust-boundary validation.
43. <don't know> Define mapping from WorkRecord, WorkAttempt, operation, invocation, plan, and curd references to Milknado graph, goal, task, node, and run provenance.
44. <don't know> Define schema-version negotiation, capability advertisement, minimum and maximum supported versions, and compatibility failure details.
45. <don't know> Define rejection, fallback, and no-work behavior for unsupported schema features, missing capabilities, invalid plans, digest conflicts, and oversized curds.
46. <don't know> Define graph persistence and recovery links to Easy Cheese invocation checkpoints and outcomes without making graph state part of `CurdPlan`.
47. <don't know> Define curd result aggregation from task and node outcomes, including aggregate acceptance verification and partial runtime failure.
48. <don't know> Define executor configuration references or snapshots, precedence resolution, immutable resolved configuration, and redaction of secrets.
49. <don't know> Define deterministic physical grouping and deduplication inputs, ambiguity detection, and the boundary where an agent planner may be invoked.
50. <don't know> Define admission and result-adapter behavior for identical replay, digest conflict, partial import, executor unavailability, and cross-database runtime references.

### Schema evolution, validation, and fixtures

51. <don't know> Draft exact Pydantic fields, enums, discriminators, conditional requirements, closed-object rules, and version identifiers for every request, result, envelope, checkpoint, outcome, WorkRecord, compaction, continuation, and adapter type.
52. <don't know> Define schema evolution and compatibility policy, including additive changes, breaking-version rules, unknown-field handling, and negotiation across Easy Cheese and Milknado releases.
53. <don't know> Decide whether the existing bounded `PhaseContract` vocabulary remains for human-authored phase payload declarations, compiles from JSON Schema, or is superseded by the shared Pydantic and JSON Schema source.
54. <don't know> Specify generated pure-Python validator architecture, constraint coverage, error-path format, recursion and size bounds, and packaging inside `cheese.pyz`.
55. <don't know> Define the positive, negative, partial, replay, identity-conflict, stale-revision, crash-recovery, and cross-version fixture matrix.
56. <don't know> Choose fixture and generated-schema ownership, paths, publication or vendoring strategy, version pinning, and cross-repository update workflow.
57. <don't know> Prove Pydantic, generated validators, Easy Cheese producers and consumers, and Milknado producers and consumers agree on every fixture.

### Delivery, migration, and follow-up

58. <don't know> Draw the exact boundary between the Easy Cheese spec, Milknado spec, and shared compatibility matrix so requirements have one owner.
59. <don't know> Finalize implementation dependency order and cumulative quality gates across schema generation, validators, producers, consumers, adapters, orchestration, and migration.
60. <don't know> Complete the adversarial pass over every earlier accepted decision and mark each relevant ADR plus PR #331 and PR #358 section as retained, amended, rejected, or superseded.
61. <don't know> Define migration from positional handoff notes, the PR #331 WorkRecord model, and existing Wheypoint provenance into the new WorkRecord and CompactionRecord authority.
62. <don't know> Define backwards-compatible rendering and `/cheese --continue` behavior during migration while preventing legacy notes from becoming a second authority.
63. <don't know> Create the Milknado curd-local physical-splitting follow-up only after its boundary contract is fixed.
64. <don't know> Ensure that follow-up preserves curd acceptance semantics, keeps subnodes inside one curd goal/task group, uses deterministic split inputs, and aggregates verification into one `CurdResult`.

## Artifacts

- <certain> Primary continuation note: `.cheese/notes/root-cheese-milknado-orchestration.md`.
- <certain> Adversarial decision audit: `.cheese/notes/root-cheese-milknado-decision-audit.md`.
- <certain> Durable envelope research: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/research/agentic-invocation-envelope-patterns/agentic-invocation-envelope-patterns.md`.
- <certain> Durable identity and retry research: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/research/operation-invocation-retry-identity/operation-invocation-retry-identity.md`.
- <certain> Easy Cheese orchestration PR under examination: <https://github.com/paulnsorensen/easy-cheese/pull/358>.
- <certain> Open stacked cross-skill contract PR: <https://github.com/paulnsorensen/easy-cheese/pull/331>.
- <certain> Use the durable research reports for external citations instead of copying source extracts into this checkpoint.

## Suggested skills

- <certain> Resume with `/cheese --continue root-cheese-milknado-orchestration`; the gated handoff returns to `/mold` and first confirms or rejects pre-terminal recovery option A.
- <certain> Continue the remaining forks in the order listed: checkpoint and recovery, identity, WorkRecord and continuation, artifacts and results, planner and review, Milknado adapter, validation, then delivery and migration.
- <certain> After explicit approval of both specs and the shared fixture matrix, use `/cook` in dependency order, then `/press` and `/age` for each repository.
- <certain> Use `/to-issues` for the Milknado splitter follow-up only after its boundary contract is fixed.

## Environment

- <certain> Checkpoint refreshed at `2026-07-29T08:58:33Z`.
- <certain> Repository: `/home/paul/Dev/easy-cheese`, branch and revision `main@3a53fc9`, tracking `origin/main`.
- <certain> Related repository: `/home/paul/Dev/milknado`, branch and revision `main@c7c1cf9`, tracking `origin/main`.
- <certain> The only observed Easy Cheese status entry was untracked `.claude/`; the only observed Milknado status entry was untracked `.serena/`.
- <certain> `just check` passes: 770 Python tests with 1 skipped, 371 shared tests, 576 fanout tests, 31 Hard Cheese tests, 35 Pasteurize tests, 5 Node tests, 98 install Bats tests, 18 fanout Bats tests, 65 Rust tests, strict validation, and the documentation build.
- <certain> The Wheypoint is normally gitignored; the dedicated checkpoint branch force-adds only this note by explicit user request.