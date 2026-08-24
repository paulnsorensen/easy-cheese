
# Milknado executor recovery

Status: locked decisions; implementation spec pending (workflow-contracts roadmap F002)
Source: extracted from the protocol reconstruction checkpoint preserved on [PR #370](https://github.com/paulnsorensen/easy-cheese/pull/370) (`.cheese/notes/root-cheese-milknado-full-protocol-reconstruction.md`, sections "Operation and invocation identity" through "Normal execution and checkpoints", "Later executor-recovery slice", and decision-dossier Fork 5)

These are the locked Step 3 decisions for the deferred executor-recovery slice — the `OperationInvocation`/`OperationCheckpoint`/`OperationOutcome` family and `recover(RecoveryRequest) -> RecoveryResult`. They bound the future F002 spec; the shipped Wheypoint continuity kernel (ADRs 001-004) is unaffected. Until that spec exists, this page is the durable authority for these decisions.

## Operation and invocation identity

- <certain> The generic execution shape is OperationInvocation<TRequest> to zero or more OperationCheckpoint<TResult> records to one OperationOutcome<TResult>.
- <certain> Operation is the correct term because the executor may be an agent, deterministic code, or a workflow.
- <certain> operation_id identifies one immutable semantic request.
- <certain> invocation_id identifies one admitted execution of that operation.
- <certain> Transport replay and Milknado-internal transient retries remain inside the current invocation until terminalization.
- <certain> A retry after terminalization creates a new invocation under the same operation.
- <certain> A semantic change to goal, subject, intent, or acceptance contract creates a new operation.
- <certain> Changing executor strategy, model, limits, runtime environment, or retry creates a new invocation without changing the operation.
- <certain> Execution status and domain-result status remain separate.
- <certain> A failed, cancelled, timed-out, or lost invocation may still carry its latest schema-valid partial result.
- <certain> Failure before the first valid checkpoint may carry no domain result.
- <certain> Domain result types own their partial-completion ledgers.

## Execution and handoff IDs

- <certain> Execution operation_id and Handoff operation_id are always distinct.
- <certain> Execution operation_id names the semantic request.
- <certain> Handoff operation_id is a commit-idempotency key for applying one continuity transition.
- <certain> Handoff provenance links the related execution invocation IDs and terminal outcome digest.
- <certain> Easy Cheese IDs and Milknado IDs remain separate namespaces.
- <certain> Milknado run_id is task-dispatch provenance and never aliases invocation_id.

## Lost-executor recovery

- <certain> A failed, lost, cancelled, or timed-out invocation never reopens.
- <certain> Recovery creates exactly one successor invocation under the same operation.
- <certain> A unique predecessor_invocation_id enforces at most one successor.
- <certain> Timeout or unresponsiveness triggers termination of the runtime-owned process group: TERM, grace period, KILL if needed, then confirmation that the process is gone.
- <certain> Only confirmed termination permits predecessor terminalization, managed-worktree transfer, and successor admission.
- <certain> If termination cannot be confirmed, recovery becomes manual and no successor is admitted.
- <certain> The predecessor's terminal status preserves the initiating cause: timed_out, cancelled, lost, or failed; forced kill is diagnostic detail.
- <certain> Recovery resumes the work, not the old transcript or uncertain agent.
- <certain> A successor starts a fresh Codex or Claude session seeded only from durable state.
- <certain> Crash-time transcript resume and session forking are excluded.
- <certain> The existing managed worktree transfers to the successor only after confirmed termination.
- <certain> Recovery may proceed from the surviving managed worktree when no checkpoint exists.
- <certain> The successor receives the original request, worktree identity and status, predecessor terminal cause, and latest checkpoint when present.
- <certain> Old transcript and progress events are excluded from the successor seed.
- <certain> The runtime records a canonical worktree fingerprint at confirmed termination covering HEAD, index, tracked content, and untracked content; ignored files are excluded.
- <certain> The runtime recomputes that fingerprint immediately before successor admission.
- <certain> Any mismatch requires manual recovery.
- <certain> Automatic v1 recovery covers runtime-owned protocol state, managed worktrees, and Git state only.
- <certain> Arbitrary unmanaged external effects require manual recovery.
- <certain> V1 has no generic effect taxonomy, reconciliation plugin system, public ReconciliationEvidence type, recovery-hold entity, central coordinator service, or fencing epoch.
- <certain> The active invocation_id gates protocol writes; the proposed fence_token was removed from v1.

## Normal execution and checkpoints

- <certain> One normal Ralph iteration remains inside the same Milknado run and invocation.
- <certain> Ralph iteration progress stays Milknado-local; the shared protocol has no ProgressEvent.
- <certain> A known-exclusive normal continuation may resume the same harness session.
- <certain> Uncertain, failed, lost, or recovered execution never resumes the old harness session.
- <certain> Checkpoints occur at explicit durable domain boundaries, not after every Ralph iteration.
- <certain> Every checkpoint is a complete schema-valid snapshot rather than a delta.
- <certain> Checkpoint history is append-only; every terminal outcome is self-contained, while retained checkpoint references preserve digest and provenance rather than reconstruction deltas.[^checkpoint]
- <certain> The admitting runtime atomically assigns checkpoint identity and order, validates the snapshot, and computes its canonical digest.
- <certain> Repeating identical checkpoint content returns the latest matching checkpoint.
- <certain> Changed checkpoint content creates the next checkpoint.
- <certain> Checkpoint retention is reachability-based.
- <certain> Retain checkpoint data while the operation remains recoverable or a successor or outcome requires the reference to resolve.
- <certain> A terminal outcome permanently retains checkpoint digest and provenance.
- <certain> Unreferenced checkpoint data may be garbage-collected after terminal operation completion.
- <certain> Configurable extra checkpoint history is excluded from v1.

## Later executor-recovery slice

- <certain> The later bounded family remains OperationInvocation, OperationCheckpoint, OperationOutcome, RecoveryRequest, and RecoveryResult.
- <certain> Recovery uses a runtime-private journal behind recover(RecoveryRequest) -> RecoveryResult.
- <certain> predecessor_invocation_id is the natural recovery idempotency key; V1 has no separate recovery request ID or public RecoveryRecord.
- <certain> The wider protocol and Milknado requirements remain preserved above and must be linked from later specs rather than silently discarded.

## Open question: package and schema version negotiation

Unresolved fork carried out of the checkpoint's decision dossier; the F002 spec must settle it.

- <certain> Option A pins a compatible Python-package version range and verifies schema IDs plus fixture compatibility.
- <certain> Option B pins exact artifact digests for generated schemas and fixtures in addition to package version.
- <certain> Option C consumes whichever contract version is latest at runtime.
- <speculative> Option B offers the strongest reproducibility but adds update ceremony.
- <certain> Option C conflicts with deterministic recovery and repeatable fixture validation.
- <don't know> No prior user decision selects Option A versus B.

[^checkpoint]: `.cheese/notes/root-cheese-milknado-orchestration.md` at `d7bd4267871e6f5e360225a5ebed8e4eb9cd3fce`:67-80; ingested before tracked source removal on 2026-08-23.

_Source: protocol reconstruction checkpoint on PR #370; `.cheese/notes/root-cheese-milknado-orchestration.md` · Updated: 2026-08-23 · Supersedes: July tentative fencing and recovery forks with the locked lost-executor rules above._
