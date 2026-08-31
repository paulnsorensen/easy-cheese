# The `WheypointDelta` contract

Every field the `commit` command accepts, and every rule that decides whether it is applied. The runtime refuses a malformed delta rather than repairing it, so build the delta to this contract instead of retrying against error text.

## Shape

```json
{
  "work_id": "auth-retry-backoff",
  "expected_revision_id": "rev-1a2b3c4d5e6f",
  "orientation": "One or more lines; the first line becomes the record title at genesis.",
  "working_context": ["src/auth/retry.py", "PR#412"],
  "next_action": {"move": "cook", "orientation": "Land the backoff ceiling.", "artifact": ".cheese/specs/auth-retry-backoff.md"},
  "decision_dossier": [
    {"fork": "Ceiling or jitter first",
     "options": [{"option": "ceiling", "evidence": ["src/auth/retry.py:88"], "breaks": "burst callers"}],
     "prior_leaning": "ceiling"}
  ],
  "add_decisions": [{"kind": "decision", "summary": "Cap the backoff at 30s.", "blocks_continuation": false}],
  "add_questions": [{"kind": "question", "summary": "Do we jitter?", "blocks_continuation": true}],
  "add_blockers": [{"kind": "blocker", "summary": "Staging is down.", "blocks_continuation": true}],
  "add_artifact_links": [{"path": ".cheese/specs/auth-retry-backoff.md", "digest": "sha256:<64 hex>", "revision_id": "rev-1a2b3c4d5e6f", "covers_entry_ids": ["q-0f1e2d3c4b5a"]}],
  "transitions": [{"entry_id": "q-0f1e2d3c4b5a", "action": "resolve", "rationale": "Answered in the spec.", "target_entry_id": null}],
  "compacted": false,
  "compaction": null,
  "session_provenance": {"harness": "claude", "session_id": "abc123", "captured_at": "2026-08-30T12:00:00Z"}
}
```

## Fields

- **`work_id`** (required) — the work this delta writes to. Also a single path segment under the corpus.
- **`expected_revision_id`** (required) — the revision you rehydrated, or the literal `"genesis"` sentinel when this work has no record. Any other value that is not the current revision is refused as a stale parent; re-read with `show` and rebuild.
- **`orientation`** — free text. At genesis its first line becomes the record title.
- **`working_context`** — a **list of strings**, not a paragraph.
- **`next_action`** — `{move, orientation, artifact}`. `move` is one of `mold`, `cut`, `cook`, `press`, `age`, `cure`, `affinage`, `briesearch`, `culture`, `hold`, `tasks`, `done`.
- **`decision_dossier`** — a list of forks: `{fork, options: [{option, evidence: [...], breaks}], prior_leaning}`.
- **`add_decisions` / `add_questions` / `add_blockers`** — lists of `ProposedEntry` `{kind, summary, blocks_continuation}`. **No `entry_id`**: the runtime derives it from the parent revision and the proposal, so the same proposal against the same parent always gets the same id.
- **`add_artifact_links`** — `{path, digest, revision_id, covers_entry_ids}`. `revision_id` must name a revision in this work's proven ancestry, and `digest` must still match the file, or lint reports the coverage claim invalid.
- **`transitions`** — `{entry_id, action, rationale, target_entry_id}`, at most one per entry. `action` is `resolve`, `supersede`, or `withdraw`; `target_entry_id` is required for `supersede` and forbidden otherwise. This is the only way a protected entry changes state; nothing removes one.
- **`compacted`** / **`compaction`** — see below.
- **`session_provenance`** — `{harness, session_id, captured_at}`, all optional individually. `captured_at` becomes the record's `created` at genesis.

## Rules

- **Omission carries forward, `[]` replaces with nothing.** `null` (or an absent field) means "unchanged"; an explicit empty list clears. The `add_*` fields only ever add.
- **Identifiers** match `[a-z0-9][a-z0-9._-]{0,63}`. **Digests** are `sha256:` followed by 64 lowercase hex characters.
- **Text fields** are at most 2000 characters. **Lists** hold at most 64 items; the protected-entry ledgers hold at most 192.
- **`blocks_continuation` must be `false` for `kind: decision`.** A decision is a record of a choice already made, so it cannot gate a resume; only questions and blockers can.
- **Genesis** (`expected_revision_id: "genesis"`) must carry `orientation`, `working_context`, `next_action`, and `session_provenance.captured_at` — there is no parent to carry them from, and the runtime reads no clock. It must **not** carry `transitions` (no entries exist yet) or `compacted` (no revision to rehydrate from). It is refused outright once the work directory holds any record or revision.
- **A dossier and a gate travel together.** An active entry with `blocks_continuation: true` derives `status: gated:` and requires a non-empty `decision_dossier`; an empty dossier requires no open gate.
- **A compacted delta must prove rehydration.** With `compacted: true`, `compaction` is required and must carry `rehydrated_from_revision_id` equal to the **current** revision, `rehydrated_record_digest` equal to that record's digest, and `reconciled_entry_ids` accounting for every protected entry the record still holds. `reconciliation_source_session_ids` is provenance and selects nothing.
- **`prior_compaction_revision_id` is forbidden in a delta.** The runtime derives it by walking the receipts on disk, because a compacted session's memory of that lineage is exactly what was lost. Sending it is refused.
- **Replay is by fingerprint.** An identical request against the same parent returns the receipt it already produced instead of writing twice, so a resubmission after a timeout is safe. A *different* request against a superseded parent is a stale-parent refusal.
