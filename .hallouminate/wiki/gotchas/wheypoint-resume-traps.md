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
