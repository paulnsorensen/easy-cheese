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
- `notes` holds at most 6000 characters; `lint` warns `notes-long` above 4000.
- **`next`** accepts `mold`, `cut`, `cook`, `press`, `age`, `cure`, `affinage`, `briesearch`, `culture`, `hold`, `tasks`, or `done`.
- **`artifact`** rides beside `next`; `affinage` needs `PR#<n>` or a PR URL, and `cook` or `cut` need a path.
- **`entries`** holds `ProposedEntry` values of kind `decision`, `question`, `blocker`, or `directive`.
- Each entry has `{kind, summary, rationale?, quote?, blocks_continuation}`.
- Only a question or a blocker can set `blocks_continuation: true`.
- A `directive` carries the user's words verbatim in `quote`.
- The runtime derives each `entry_id` from the parent and the proposal.
- **`decision_dossier`** holds forks `{fork, options: [{option, evidence, breaks}], prior_leaning}`.
- A fork may describe any active question; every gating entry needs a covering fork.
- A `decision_dossier` merges into the carried dossier by fork title; a fork with a carried title replaces that fork in place.
- **`remove_dossier_forks`** names carried fork titles to drop before the merge; an unknown title is refused as `unknown-dossier-fork`.
- **`artifact_links`** holds `{path, ref?, covers_entry_ids?}`; the runtime computes the digest and pins the revision.
- `ref` is a typed ref; see the scheme table in [`work-graph.md`](work-graph.md).
- A link without `ref` reads as `repo:<path>`.
- A link replaces the carried link with the same normalized ref; links are a set keyed by that ref.
- A `milknado:` or `https:` link carries no digest; a `covers_entry_ids` on it is refused as `unpinnable-scheme`.
- An unpinned `wheypoint:` link is pinned to the target's current revision at commit.
- **`remove_artifact_links`** names carried paths to drop; an unknown path is refused.
- An empty `artifact_links` or `remove_artifact_links` list is refused.
- **`add_edges`** holds `{to, kind, rationale?}`; the host stamps `revision_id` at commit and ignores a supplied value.
- **`remove_edges`** holds `{to, kind}` keys of carried edges to drop.
- Edges are a set keyed by `(to, kind)`; [`work-graph.md`](work-graph.md) lists each `kind`.
- An intent never adds or removes a `forked_from` or `forked_to` edge; `fork` and the host own them.
- **`transitions`** holds `{entry_id, action, rationale, target_entry_id}`; `action` is `resolve`, `supersede`, or `withdraw`.
- Only a transition changes a protected entry's state; no operation removes one.
- **`tasks`** and **`parallel`** carry independent moves when `next` is `tasks`; see [`parallel-handoffs.md`](parallel-handoffs.md).
- **`base_revision_id`** pins the revision the intent was written against; omit it to bind the current revision.
- **`session`** holds optional `{harness, session_id, captured_at}`.

## Rules

- Omission carries data forward; `null` means unchanged.
- An explicit empty `working_context` or `decision_dossier` replaces the carried value with nothing.
- Identifiers match `[a-z0-9][a-z0-9._-]{0,63}`.
- Text fields other than `notes` contain at most 2000 characters; lists at most 64 items.
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

## Flag form

`checkpoint` and `validate` build or overlay the intent from flags.
With an intent file, each flag extends or replaces the matching key of that file.
Without an intent file, the flags build the whole intent.
With flags, the positional may be a work id instead of an intent file.
With flags and no intent argument, a piped intent needs `-`; otherwise the command refuses `intent-ambiguous`.

- `--work-id`, `--orientation`, `--next`, `--artifact`, and `--notes-file` set one scalar each.
- `--question` and `--blocker` add entries; `--gates` makes every one of them in the call block continuation.
- `--decision` adds a decision, and `--directive` adds a directive with the paired `--quote`.
- `--resolve` and `--withdraw` add transitions for carried entry ids.
- `--rationale` values pair in order with each `--decision`, then each `--resolve`, then each `--withdraw`.
- `--context` adds a `working_context` path.
- `--link` adds an edge with the paired `--kind`; a pinnable ref also adds an artifact link.
- `--covers` applies to every pinnable `--link` in the call.
- `--covers` omitted keeps the stored coverage.

The flag form refuses with these codes:

- `flag-pairing`: the `--rationale` count differs from the decisions, resolves, and withdraws, a `--quote` or `--kind` count differs from its pair, `--gates` has no question or blocker, or `--covers` has no pinnable `--link`.
- `flag-kind`: a `--kind` names no edge kind.
- `flag-link`: a `--link` is not a valid typed ref.
- `flag-conflict`: the intent file holds a non-list value at a key a flag extends.
- `notes-unreadable`: the `--notes-file` could not be read.
- `intent-ambiguous`: the positional work id differs from `--work-id`, or flags without an intent argument meet a piped intent.
- `intent-unreadable`: the positional is neither an intent file nor a work id.

## `next:` values

- `mold`, `cut`, `cook`, `press`, `age`, `cure`: the next pipeline phase.
  `next: cook` on a standalone checkpoint names the phase to resume; it does not publish a Cook→Cook phase artifact.
- `affinage`: PR review comments or failing CI; `artifact` names the PR.
- `briesearch`, `culture`: a read-only next move that `/cheese --continue` dispatches.
- `tasks`: independent moves; see [`parallel-handoffs.md`](parallel-handoffs.md).
- `hold`: restore orientation and wait for instructions.
- `done`: the work is complete; the checkpoint is a record, not a baton.
## Reply envelope

A success reply prints one indented JSON document to stdout: `{"ok": true, "command": "<name>", ...fields}`.
A refusal writes one JSON line to stderr and prints nothing to stdout: `{"error": "<code>: <message>", "exit_code": 1}`.

- **`checkpoint`** returns `note_path`, `replayed`, `work_id`, `revision_id`, `revision_number`, `parent_revision_id`, `status`, `durability`, `projection_path`, `record`, `revision`, `markdown`, `derived_entry_ids`, `applied_transitions`, `applied_edges`, and `removed_edges`.
- **`validate`** returns `valid` and `work_id`.
- **`schema`** returns `slug` and `schema`.
- **`resolve`** returns `ref`, `outcome`, `dispatchable`, `source`, `work_id`, `record`, `projection`, `findings`, `matches`, `searched`, `legacy_note`, `legacy_slug`, `phase_slug`, `detail`, `pending`, `bridge`.
- **`show`** returns `work_id`, `status`, `revision_id`, `revision_number`, `record`, `pending`, `bridge`.
- **`fork`**, **`link`**, **`unlink`**, **`shape`**, and **`backlinks`** replies are in [`work-graph.md`](work-graph.md).
- **`lint`** returns `path`, `clean`, `findings`, `projection`.
- **`list`** returns `corpus_root`, `items`, and `lines`.
- **`log`** returns `work_id`, `revisions`, `lines`, and `unreadable`.
- **`turns`** returns `transcript`, `count`, `skipped_lines`, `turns`, and `lines`.

`lines` is a list of strings, one per row, for a shell caller to read line by line.
Each `lines` entry is tab-separated columns, in a fixed order per command.
`list` columns are `work_id`, `revision_number`, `status`, `next`, `detail`.
`log` columns are `revision_number`, `revision_id`, `captured_at`, `additions`, `transitions`, `compacted`.
`turns` columns are `timestamp`, `text`.
A column value escapes a backslash as `\\`.
A column value escapes a newline as `\n`.
A column value escapes a tab as `\t`.
This escaping keeps one line one record.

`items` (from `list`) is one untyped JSON object per work item, carrying `work_id` plus either `unreadable`, `no_record`, or the record's summary fields.
`revisions` (from `log`) is one untyped JSON object per revision, carrying `revision_number`, `revision_id`, `captured_at`, `additions`, `transitions`, `compacted`.
`turns` (from `turns`) is one untyped JSON object per user turn, carrying `timestamp` and `text`.
`unreadable` (from `log`) lists `{path, reason}` for revision files the scan could not parse.
`skipped_lines` (from `turns`) counts transcript lines that could not be parsed as a turn.
`count` (from `turns`) is the number of turns returned.
`corpus_root` (from `list`) is the resolved root directory the listing scanned.

Exit `0` means the command succeeded; the reply carries the command's own fields.
Exit `1` means the command refused the request; the stderr line carries `error` and `exit_code`.
Exit `2` means the command-line usage was wrong, before any command ran.
Exit `3` means the reply violated its own schema contract.
An unexpected crash also exits `1`, but the stderr line names the exception class and points to a `traceback` file; it carries no refusal code.

Each refusal names a `code`:

- `invalid-json`: stdin was not one JSON value.
- `storage-error`: the work store could not be opened or read.
- `commit-only-field`: `checkpoint` was asked to author `compacted`, `compaction`, or `expected_revision_id` directly.
- `invalid-intent`: the intent payload failed schema or delta validation.
- `secret-pattern`: a field looked like a credential.
- `record-unreadable`: the work's record exists but could not be parsed.
- `compaction-proof-unreadable`: the `--compacted` proof file could not be read or parsed as JSON.
- `invalid-compaction-proof`: the `--compacted` proof failed schema validation.
- `genesis-conflict`: a genesis commit collided with an existing record.
- `stale-parent`: the intent's parent revision has moved on.
- `commit-refused`: the commit kernel refused the delta for another reason.
- `note-unwritable`: the note directory or mirror file could not be written.
- `pending-corrupt`: a pending-mirror ledger entry named a different request than its revision.
- `unknown-contract`: `schema` was asked for a slug with no registered contract.
- `record-missing`: `show` or `log` found no record for the work id.
- `store-inconsistent`: `log` found a record but every revision file was dropped as unreadable.
- `session-required`: `turns` was given neither `--session` nor `--transcript`.
- `invalid-session`: the given `--session` id was not a safe file-name segment.
- `transcript-missing`: no transcript file exists at the resolved path.
- `invalid-reference`: `resolve` could not interpret the given reference.
- `flag-pairing`, `flag-kind`, `flag-link`, `flag-conflict`, `notes-unreadable`: the flag form refused; see [Flag form](#flag-form).
- `unpinnable-scheme`, `unknown-edge`, `host-only-edge`, `unknown-dossier-fork`: the commit kernel refused a ref, an edge, or a dossier title.
