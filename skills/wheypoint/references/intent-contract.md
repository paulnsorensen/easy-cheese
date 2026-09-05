# The `CheckpointIntent` contract

`checkpoint` accepts one intent and derives everything else.

Run `schema checkpoint-intent` for the generated JSON Schema.

Run `validate` for a schema-only dry run that never opens the store.

## Shape

```json
{
  "work_id": "auth-retry-backoff",
  "orientation": "One or more lines; the first line becomes the record title at genesis.",
  "working_context": ["src/auth/retry.py", "PR#412"],
  "notes": "The report a cold reader needs, as Markdown.",
  "next": "cook",
  "artifact": ".cheese/specs/auth-retry-backoff.md",
  "entries": [
    {"kind": "decision", "summary": "Cap the backoff at 30s.", "rationale": "Burst callers saturate the pool."},
    {"kind": "directive", "summary": "Prose stays STE100.", "quote": "is it all in STE100?"},
    {"kind": "question", "summary": "Do we jitter?", "blocks_continuation": true},
    {"kind": "blocker", "summary": "Staging is down.", "blocks_continuation": true}
  ],
  "decision_dossier": [
    {"fork": "Ceiling or jitter first",
     "options": [{"option": "ceiling", "evidence": ["src/auth/retry.py:88"], "breaks": "burst callers"}],
     "prior_leaning": "ceiling"}
  ],
  "artifact_links": [{"path": ".cheese/specs/auth-retry-backoff.md", "covers_entry_ids": []}],
  "remove_artifact_links": [".cheese/cook/stale.md"],
  "transitions": [{"entry_id": "q-0f1e2d3c4b5a", "action": "resolve", "rationale": "Answered in the spec.", "target_entry_id": null}],
  "tasks": null,
  "parallel": null,
  "base_revision_id": null,
  "session": {"harness": "claude", "session_id": "abc123", "captured_at": "2026-09-05T12:00:00Z"}
}
```

## Fields

- **`work_id`** is required and becomes one path segment under the corpus.
- **`orientation`** is free text; its first line becomes the title at genesis.
- **`working_context`** is a list of pointers, not a paragraph.
- **`notes`** is the Markdown body the projection renders under `## Notes`; omission carries it forward.
- **`next`** accepts `mold`, `cut`, `cook`, `press`, `age`, `cure`, `affinage`, `briesearch`, `culture`, `hold`, `tasks`, or `done`.
- **`artifact`** rides beside `next`; `affinage` needs `PR#<n>` or a PR URL, and `cook` or `cut` need a path.
- **`entries`** holds `ProposedEntry` values of kind `decision`, `question`, `blocker`, or `directive`.
- Each entry has `{kind, summary, rationale?, quote?, blocks_continuation}`.
- Only a question or a blocker can set `blocks_continuation: true`.
- A `directive` carries the user's words verbatim in `quote`.
- The runtime derives each `entry_id` from the parent and the proposal.
- **`decision_dossier`** holds forks `{fork, options: [{option, evidence, breaks}], prior_leaning}`.
- A fork may describe any active question; every gating entry needs a covering fork.
- **`artifact_links`** holds `{path, covers_entry_ids?}`; the runtime computes the digest and pins the revision.
- A link replaces the carried link with the same path; links are a set keyed by path.
- **`remove_artifact_links`** names carried paths to drop; an unknown path is refused.
- An empty `artifact_links` or `remove_artifact_links` list is refused.
- **`transitions`** holds `{entry_id, action, rationale, target_entry_id}`; `action` is `resolve`, `supersede`, or `withdraw`.
- Only a transition changes a protected entry's state; no operation removes one.
- **`tasks`** and **`parallel`** carry independent moves when `next` is `tasks`; see [`parallel-handoffs.md`](parallel-handoffs.md).
- **`base_revision_id`** pins the revision the intent was written against; omit it to bind the current revision.
- **`session`** holds optional `{harness, session_id, captured_at}`.

## Rules

- Omission carries data forward; `null` means unchanged.
- An explicit empty `working_context` or `decision_dossier` replaces the carried value.
- Identifiers match `[a-z0-9][a-z0-9._-]{0,63}`.
- Text fields contain at most 2000 characters; lists at most 64 items.
- A first checkpoint must carry at least one entry or a `notes` body.
- An unknown key at any depth is refused and named by path.
- Text that matches a credential pattern is refused and named by field.
- An identical intent against the same parent replays the existing receipt.
- A changed intent against a superseded parent is refused as stale.

## Compaction proof

After a context compaction, rehydrate with `show`, then pass `--compacted <proof.json>`.

The proof is a `CompactionRecord`: `{rehydrated_from_revision_id, rehydrated_record_digest, reconciled_entry_ids}`.

`rehydrated_from_revision_id` must equal the current revision and `rehydrated_record_digest` its record digest.

`reconciled_entry_ids` must include every protected entry in the record.

The runtime derives `prior_compaction_revision_id` from stored receipts and refuses a supplied value.
