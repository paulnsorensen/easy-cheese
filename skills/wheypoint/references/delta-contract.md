# WheypointDelta JSON contract

Author a delta from this contract or inspect the bundled machine-readable form with
`python3 skills/wheypoint/scripts/wheypoint.pyz commit --schema`. Pipe exactly one JSON
object to `commit`; the runtime rejects unknown fields and invalid nested values.

## Carry-forward semantics

`work_id` and `expected_revision_id` are always required. Every other field is optional.
Omitted or `null` means **carry the current value forward unchanged**. For list-valued
fields, `[]` means **replace the value with no items**. Those requests are intentionally
different.

Identifiers (`work_id`, `expected_revision_id`, `session_id`, entry IDs, and revision
pins) match `[a-z0-9][a-z0-9._-]{0,63}`. Non-empty text is limited to 2,000 characters,
and lists are limited to 64 items. A digest has the form `sha256:<64 lowercase hex>`.

## Complete field shape

| Field | Shape | Meaning |
| --- | --- | --- |
| `work_id` | identifier | Stable identity of the work record. |
| `expected_revision_id` | identifier | `genesis` for the first record; otherwise the current `revision_id` returned by `show`. |
| `orientation` | string or `null` | Current situation for a cold reader. |
| `working_context` | string array or `null` | Relevant files, artifacts, and state. |
| `next_action` | `NextAction` or `null` | `{move, orientation, artifact}`; `artifact` may be `null`. |
| `decision_dossier` | `DecisionFork[]` or `null` | Open forks; each has `fork`, non-empty `options`, and optional `prior_leaning`. |
| `add_decisions` | `ProposedEntry[]` or `null` | Decisions to add. The runtime assigns each `entry_id`. |
| `add_questions` | `ProposedEntry[]` or `null` | Questions to add. |
| `add_blockers` | `ProposedEntry[]` or `null` | Blockers to add. |
| `add_artifact_links` | `ArtifactLink[]` or `null` | Pinned or unpinned supporting artifacts. |
| `transitions` | `EntryTransition[]` or `null` | Explicitly resolve, supersede, or withdraw protected entries. |
| `compacted` | boolean | Whether this delta follows context compaction; defaults to `false`. |
| `rehydrated_from_revision_id` | identifier or `null` | Required evidence for a compacted delta and forbidden otherwise. |
| `session_provenance` | object or `null` | `{harness, session_id, captured_at}`; each field may otherwise be `null`. |

Nested vocabularies and invariants:

- `NextAction.move`: `mold`, `cut`, `cook`, `press`, `age`, `cure`, `affinage`,
  `briesearch`, `culture`, `hold`, `tasks`, or `done`.
- `ProposedEntry`: `{kind, summary, blocks_continuation}` where `kind` is `decision`,
  `question`, or `blocker`. Do not provide `entry_id`; the runtime assigns it.
  `blocks_continuation` defaults to `false` and must be `false` for a decision.
  Entries in `add_decisions`, `add_questions`, and `add_blockers` must use the
  matching `kind`. Any gating question or blocker requires a non-empty
  `decision_dossier` describing the open fork.
- `ArtifactLink`: `{path, digest, revision_id, covers_entry_ids}`. `digest` and
  `revision_id` may be `null`; `covers_entry_ids` defaults to `[]`.
- `EntryTransition.action`: `resolve`, `supersede`, or `withdraw`. Every transition has
  `{entry_id, action, rationale, target_entry_id}`. `target_entry_id` is required only
  for `supersede` and must otherwise be omitted or `null`.
  A delta may transition each active existing entry at most once; a `supersede`
  target must name the successor entry.
- `DecisionFork.options[]`: `{option, evidence, breaks}`. `evidence` is a string array.

## Genesis example

The literal genesis sentinel is `"genesis"`. A genesis delta must include
`orientation`, `working_context`, `next_action`, and `session_provenance.captured_at`.
It cannot set `compacted: true` or carry non-empty `transitions` because no prior record
exists.

```json
{
  "work_id": "issue-423-wheypoint",
  "expected_revision_id": "genesis",
  "orientation": "The delta contract and canonical projection path are being fixed.",
  "working_context": [
    "skills/wheypoint/SKILL.md",
    "src/wheypoint/wheypoint.py"
  ],
  "next_action": {
    "move": "cook",
    "orientation": "Implement and verify issue 423.",
    "artifact": ".cheese/specs/issue-423-wheypoint-delta-contract.md"
  },
  "decision_dossier": [],
  "add_decisions": [
    {
      "kind": "decision",
      "summary": "The canonical store remains authoritative.",
      "blocks_continuation": false
    }
  ],
  "add_questions": [],
  "add_blockers": [],
  "add_artifact_links": [],
  "session_provenance": {
    "harness": "claude-code",
    "session_id": "session-20260815",
    "captured_at": "2026-08-15T21:35:33Z"
  }
}
```

The runtime derives the record's `created` value from `session_provenance.captured_at`;
it does not read the wall clock.

## Non-genesis example

This update carries `orientation`, decisions, questions, and blockers forward because
those fields are omitted or `null`. It deliberately clears `working_context` with `[]`,
resolves one existing question, and adds a pinned artifact.

```json
{
  "work_id": "issue-423-wheypoint",
  "expected_revision_id": "rev-0123456789ab",
  "orientation": null,
  "working_context": [],
  "next_action": {
    "move": "age",
    "orientation": "Review the completed issue 423 change.",
    "artifact": null
  },
  "add_artifact_links": [
    {
      "path": "skills/wheypoint/references/delta-contract.md",
      "digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "revision_id": null,
      "covers_entry_ids": ["q-0123456789ab"]
    }
  ],
  "transitions": [
    {
      "entry_id": "q-0123456789ab",
      "action": "resolve",
      "rationale": "The shipped contract now answers the question.",
      "target_entry_id": null
    }
  ],
  "session_provenance": {
    "harness": "claude-code",
    "session_id": "session-20260815",
    "captured_at": "2026-08-15T22:00:00Z"
  }
}
```

For a compacted non-genesis delta, set `compacted: true` and set
`rehydrated_from_revision_id` to the current revision returned by `show`. The commit is
rejected if that revision is no longer current.
