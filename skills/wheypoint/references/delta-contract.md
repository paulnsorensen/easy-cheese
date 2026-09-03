# The `WheypointDelta` contract

This contract defines each field that `commit` accepts. It also defines each application rule. The runtime refuses malformed deltas. Build each delta to this contract.

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

- **`work_id`** (required): Identifies the work. It is one path segment under the corpus.
- **`expected_revision_id`** (required): Names the rehydrated revision. Use `"genesis"` when the work has no record. The runtime refuses another value when it is not current. Run `show` again and rebuild the delta.
- **`orientation`**: Contains free text. Its first line becomes the record title at genesis.
- **`working_context`**: Contains a **list of strings**, not a paragraph.
- **`next_action`**: Contains `{move, orientation, artifact}`. `move` accepts `mold`, `cut`, `cook`, `press`, `age`, `cure`, `affinage`, `briesearch`, `culture`, `hold`, `tasks`, or `done`.
- **`decision_dossier`**: Contains forks with `{fork, options: [{option, evidence: [...], breaks}], prior_leaning}`.
- **`add_decisions` / `add_questions` / `add_blockers`**: Contain `ProposedEntry` values with `{kind, summary, blocks_continuation}`. Do not supply `entry_id`. The runtime derives it from the parent and proposal. The same proposal and parent always produce the same identifier.
- **`add_artifact_links`**: Contains `{path, digest, revision_id, covers_entry_ids}`. `revision_id` must name a revision in the proven ancestry. The digest must match the file. Lint reports an invalid coverage claim.
- **`transitions`**: Contains `{entry_id, action, rationale, target_entry_id}`. Supply at most one transition for each entry. `action` accepts `resolve`, `supersede`, or `withdraw`. `supersede` requires `target_entry_id`. Other actions forbid `target_entry_id`. Only a transition changes a protected entry's state. No operation removes a protected entry.
- **`compacted`** / **`compaction`**: See the rules below.
- **`session_provenance`**: Contains optional `{harness, session_id, captured_at}` values. `captured_at` becomes `created` at genesis.

## Rules

- **Omission carries data forward. An empty list clears data.** `null` and absent fields mean unchanged. The `add_*` fields only add entries.
- **Identifiers** match `[a-z0-9][a-z0-9._-]{0,63}`. **Digests** start with `sha256:` and contain 64 lowercase hexadecimal characters.
- **Text fields** contain at most 2000 characters. **Lists** contain at most 64 items. Protected-entry ledgers contain at most 192 items.
- **Set `blocks_continuation` to `false` for `kind: decision`.** A decision records a completed choice. Only questions and blockers can stop continuation.
- **Genesis** uses `expected_revision_id: "genesis"`. Include `orientation`, `working_context`, `next_action`, and `session_provenance.captured_at`. No parent can supply these values. The runtime does not read a clock. Do not include `transitions` because no entries exist. Do not include `compacted` because no revision exists. The runtime refuses genesis after the work directory contains a record or revision.
- **A dossier and gate occur together.** An active blocking entry derives `status: gated:`. It also requires a non-empty `decision_dossier`. An empty dossier requires no open gate.
- **A compacted delta must prove rehydration.** Set `compacted: true` and include `compaction`. `rehydrated_from_revision_id` must equal the current revision. `rehydrated_record_digest` must equal that record's digest. `reconciled_entry_ids` must include every protected entry in the record. `reconciliation_source_session_ids` records provenance and selects nothing.
- **Do not include `prior_compaction_revision_id` in a delta.** The runtime derives it from the stored receipts. A compacted session lost this lineage from memory. The runtime refuses a supplied value.
- **Replay uses the fingerprint.** An identical request against the same parent returns the existing receipt. It does not write a second revision. A different request against an old parent receives a stale-parent refusal.
