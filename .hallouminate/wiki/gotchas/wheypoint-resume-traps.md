# Wheypoint resume traps

Wheypoint resume traps are the ways a `/cheese --continue <slug>` resume silently loses or fails to find state. Cheese never reads a phase report directly; every resume goes through Wheypoint, and Wheypoint accepts only registered phase-report projections or a `.cheese/notes/` fallback. The r014 edge reviews (`edge-cook-cheese.md`, `edge-cheese-wheypoint.md`, `edge-wheypoint-cook.md`, `edge-schemas-wheypoint.md`) recorded the traps below. The continuity model itself is in [wheypoint-continuity-kernel-001](../adr/wheypoint-continuity-kernel-001.md).

## The legacy resolver searches only `.cheese/notes/`

`src/easy_cheese/skills/wheypoint/legacy.py:31,57` finds `<worktree>/.cheese/notes/<slug>.md` and nothing else. A `--continue` for a phase report at `.cheese/cook/<slug>.md` returns not-found even though the file exists. A skill that writes its own report format, such as Cure's `.cheese/cure/<slug>.md`, must register a projection with Wheypoint to be resumable; a valid preamble alone is not enough.

## A checkpoint drops fields Cheese needs

`CheckpointIntent` and `NextAction` (`src/easy_cheese_schemas/wheypoint.py:282-290`, `wheypoint/checkpoint.py:85-107`) store only move, orientation, and artifact. `mode`, `task`, `order`, `baseline`, and durable flags are accepted and discarded, and `projection.py:68-95` does not re-add them. The typed models have no `baseline` field at all, while the legacy string parser hard-rejects one with `LegacyDecodeError`. Any resume feature that needs those fields must extend the typed models first.

## Lineage integrity is enforced in two layers

The model layer rejects a later revision with no parent. `lineage.walk` (`src/easy_cheese/skills/wheypoint/lineage.py:65-102`) compares both `work_id` and `revision_number` (`parent.revision_number == revision.revision_number - 1`), so a foreign parent or a skipped revision fails. Before the r014 cure the walker checked only missing parents, cycles, and digests.

## Compaction proofs re-derive fully and point backward

`lint.py:449-475` re-derives the whole compaction proof and rejects a `prior_compaction_revision_id` that names itself or a later position in the current-first chain. A spot-check or a self-reference was a forgery vector.

## Promote only after the mirror is durable

`wheypoint/commit.py` runs the durability finalizer before `store.promote` while it holds the record lock (`commit.py:141-180`). Promoting first left a "current" record whose projection claimed `durability: repo-snapshot` after a failed mirror write. Retries are idempotent through a pending ledger keyed by request and revision identity, so an interrupted commit cannot double-append.

## `checkpoint` and `commit` both stay

`checkpoint` is the normal write path with parent binding. `commit` remains for caller-supplied raw deltas and compaction proofs. `checkpoint` refuses every legacy key; `resolve` still reads legacy notes.

_Source: r014 skill-review round notes (ingest hash 499c49c7b67d5eb6), verified against `src/easy_cheese/skills/wheypoint/` on 2026-09-04 · Updated: 2026-09-04 · Supersedes: review-time claims that lineage and compaction ordering were unenforced_


## Writer exhaustion needs a non-terminal checkpoint

The September 19, 2026 investigation finds a gap between writer budget handling and authoritative resume.
A compact worker reply is an observation set, not a Wheypoint record.
The parent owns checkpoint persistence because the exhausted worker can no longer run the required commands.
The accepted recovery contract uses one fresh writer after an authoritative resolve returns nonempty `working_context`.[^writer-recovery]

An incomplete Cook must not use the terminal phase writer to advance to Age.
The shared checkpoint kernel preserves the current phase for recovery.
The host carries completed work, remaining work, worktree identity, and the resolved source ranges into the retry.
A missing checkpoint, invalid context, or second exhaustion halts.
The parent must not implement the remainder automatically.[^writer-recovery]

[^writer-recovery]: `src/easy_cheese/shared/workflow.py` (`WriterCheckpoint`, `WriterBudgetExceeded`, `_execute_curd`); `src/easy_cheese/shared/wheypoint/checkpoint.py`; `src/easy_cheese/shared/fanout/phase_decision.py`. Recovery decision: September 19, 2026. Source verification and release status belong to the implementation PR.


The Wheypoint recovery boundary owns checkpoint validation, artifact publication, commit, rollback, and authoritative resolve.
It rejects credential-like intent text before persistence.
A directory advisory lock serializes the record read, idempotency check, publication, and commit.
Identical recovery requires matching intent, recorded digest, and stored artifact bytes.
Cleanup preserves an artifact when a committed record references it or authority cannot be read.[^recovery-publication]

The host validates the first partial result before retry dispatch.
A failed retry retains that immutable result and its original evidence digests.
The retry cannot rehash its own edits as proof of earlier completed work.[^recovery-snapshot]

An explicit repository root controls both default project identity and the checkpoint corpus.
Explicit caller overrides remain authoritative.
Recovery work identifiers include the full remote identity without changing the global project-key format.[^recovery-root]

[^recovery-publication]: src/easy_cheese/shared/wheypoint/recovery.py:161-333; tests/wheypoint/python/test_recovery.py.
[^recovery-snapshot]: src/easy_cheese/shared/workflow.py (`_validate_budget_checkpoint`, `_execute_curd`); tests/schemas/python/test_workflow_thread.py.
[^recovery-root]: src/easy_cheese/shared/write_handoff_artifact.py; src/easy_cheese/shared/wheypoint/resolve.py; src/easy_cheese/shared/workflow.py (`_budget_target_identity`, `_budget_work_id`); tests/python/test_cross_root_continuity.py.

