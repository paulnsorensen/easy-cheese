# The Wheypoint work graph

A record names other work and documents through typed refs and typed edges.
`fork`, `link`, and `unlink` write edges; `shape`, `backlinks`, and the `list` filters read them.
Each write changes only the record that starts it.
The counterpart record learns of the change on read and applies it at its own next `checkpoint`.

## Refs

A ref is an absolute URI string.
The runtime parses, normalizes, resolves, and digests it by scheme.

| Scheme | Form | Resolves to | Digest pin |
| --- | --- | --- | --- |
| `repo:` | `repo:<repo-relative path>` | a file in the bound checkout | sha256 of the bytes |
| `xdg:` | `xdg:<project_key>/<path>` | a document under the corpus home of that project | sha256 of the bytes |
| `wheypoint:` | `wheypoint:<project_key>/<work_id>[@<revision_id>][#<entry_id>]` | a record, one revision, or one entry | the target record digest at the pinned revision |
| `milknado:` | `milknado:<project_key>/<node_key>` | a Mikado node by stable key | none |
| `https:` | a PR, issue, or other URL | an external page | none |

- A wiki page is a `repo:` ref; no `wiki:` scheme exists.
- `milknado:` and `https:` refs carry no digest, and the runtime does not check that the target exists.
- A `--covers` or `covers_entry_ids` on a `milknado:` or `https:` ref is refused as `unpinnable-scheme`.
- An unpinned `wheypoint:` link is pinned to the target's current revision at commit.
- A schema-3 link that holds only `path` reads as `repo:<path>` with a normalization receipt.

## Edge kinds

An edge is `{to, kind, rationale?, revision_id}`, held by the record it starts from.
A record holds its edges as a set keyed by `(to, kind)`.
The host stamps `revision_id` at commit.

| Kind | Reciprocal | Meaning |
| --- | --- | --- |
| `forked_from` | `forked_to` | this record is a fork child of the target |
| `forked_to` | `forked_from` | the target is a fork child of this record |
| `supersedes` | `superseded_by` | this record replaces the target |
| `superseded_by` | `supersedes` | the target replaces this record |
| `implements` | none | this record implements the target |
| `informs` | none | this record informs the target |
| `checkpoints` | none | this record checkpoints a Mikado goal or task |
| `blocked_by` | none | the target blocks this record |
| `relates_to` | `relates_to` | the records relate |

- `forked_from` and `forked_to` are host-only.
- An intent, `link`, or `unlink` that names a host-only kind is refused as `host-only-edge`.
- An added edge whose rationale copies the host's reciprocal marker is also refused as `host-only-edge`.
- A `link` to a `wheypoint:` target owes the target a reciprocal edge when the kind has one.

## `fork`

```bash
python3 skills/wheypoint/scripts/wheypoint.pyz fork <parent> <child> --orientation "<child title>" [--move <id>]... [--copy <id>]... [--dossier <fork title>]... [--link <ref>]... [--context <path>]... [--notes-file <file>] [--next <move>] [--artifact <artifact>] [--project <key>]
```

- `fork` writes exactly one revision: the child genesis.
- The parent record is never written by `fork`.
- The first line of `--orientation` becomes the child title.
- `--move` names a parent entry the child takes over.
- `--copy` names a parent entry the child copies.
- When no `--move` and no `--copy` is given, active questions and blockers move, and active decisions and directives copy.
- Each child entry carries `origin = wheypoint:<project_key>/<parent>@<rev>#<entry_id>`.
- `--dossier` names a parent dossier fork, and `--link` names a parent artifact link, for the child to take.
- A moved gating entry needs a `--dossier` fork that describes it.
- The child holds a `forked_from` edge pinned to the parent's current revision.
- The reply adds `origins` (child entry id to origin ref) and `edges` to the checkpoint result.
- `--next` follows the same artifact rule as `checkpoint`; a missing `--artifact` for `cook`, `cut`, or `affinage` is refused as `invalid-intent`.
- `fork` mirrors the child projection to `.cheese/notes` and reports `repo-snapshot`, like `checkpoint`; under `--project` it writes no mirror and reports `canonical-local`.

### `fork-pending` and host-side reconciliation

`show`, `resolve`, `lint`, and `shape` scan the project corpus for children whose `forked_from` names the parent without a matching `forked_to`.
Each hit is reported as `fork-pending`, with the child ref and the affected entry ids.
The parent's next `checkpoint` applies the pending fork host-side, with no agent input:

- each moved entry becomes `forked`, with `successor` set to the child entry ref;
- each copied entry gains `copies`;
- the selected dossier forks and links leave the parent; and
- the parent gains a `forked_to` edge.

The receipt lists these changes in `applied_transitions` and `applied_edges`.
A `forked` entry never gates.
A moved gating question keeps the parent gated until that checkpoint.
An agent-authored `fork` transition is refused.

### `fork` refusal codes

- `fork-exists`: the child work id already has a record or history.
- `unknown-parent`: the parent has no record.
- `unknown-entry`: the parent holds no entry with that id.
- `already-forked`: the entry is `forked`, or a pending fork already moves it.
- `inactive-entry`: the entry is not active.
- `fork-empty`: the parent has no entry to move or copy.
- `fork-overlap`: one entry id is named twice.
- `fork-too-large`: the selection does not fit in the edge rationale.
- `fork-title`: a dossier title or link ref holds a separator the fork rationale uses.
- `unknown-dossier`: the parent has no dossier fork with that title.
- `unknown-link`: the parent carries no link with that ref.
- `dossier-required`: a moved gating entry has no `--dossier` fork.
- `record-unreadable`: the parent record could not be read.
- `note-unwritable`: the child projection mirror could not be written.

## `link` and `unlink`

```bash
python3 skills/wheypoint/scripts/wheypoint.pyz link <work-id> <ref> --kind <edge-kind> [--covers <id>]... [--rationale "<why>"]
python3 skills/wheypoint/scripts/wheypoint.pyz unlink <work-id> <ref> --kind <edge-kind>
```

- `link` adds one edge on `<work-id>` and commits one revision.
- For a pinnable ref, `link` also adds or refreshes the artifact link with the current digest and revision pin.
- `--covers` names entry ids that the pinned link covers.
- Omitting `--covers` keeps the stored coverage; `--covers` replaces it.
- The reply is the checkpoint result plus `link: {to, kind}`.
- `link` writes only the source record.
- A `wheypoint:` target reports `link-pending` on read and applies the reciprocal edge at its next `checkpoint`.
- `unlink` removes the edge keyed by `(ref, kind)` and lists it in `removed_edges`.
- An `unlink` of an edge the record does not hold is refused as `unknown-edge`.
- An explicit `unlink` sticks: reconciliation does not add the edge again until the source links again at a new revision.

## `shape`

```bash
python3 skills/wheypoint/scripts/wheypoint.pyz shape [<work-id>] [--scope project | machine] [--project <key>]... [--depth <n>] [--kind <edge-kind>]...
```

`shape` returns one JSON document; it never picks a record and never dispatches.

- `nodes`: one entry per record, with `ref`, `project`, `work_id`, `title`, `status`, `next`, `revision_number`, `updated`, and `gates`.
- `edges`: every held edge, as `{from, to, kind, revision_id, pending}`.
- `pending`: the reciprocal edges that `fork-pending` and `link-pending` owe; they have no `revision_id`.
- `documents`: each non-`wheypoint:` ref that two or more records name, with those records.
- `roots`: the node refs with no `forked_from` or `superseded_by` edge.
- `dangling`: each edge whose `wheypoint:` target has no record.
- `dot`: a deterministic Graphviz string, with nodes sorted by ref and edges by from, to, and kind.

A `<work-id>` keeps only the component around that record.
`--depth <n>` keeps records within `n` hops of `<work-id>`.
`--kind` keeps only edges of the named kinds.

## `backlinks` and the `list` filters

```bash
python3 skills/wheypoint/scripts/wheypoint.pyz backlinks <ref> [--scope project | machine] [--project <key>]...
```

`backlinks` returns `ref` and `items`: every record in scope whose edges or links name the normalized ref.
`list` adds these repeatable filters:

- `--entry-kind` and `--entry-state` keep records with a matching entry; one entry must match both.
- `--gated` keeps only gated records, and `--no-gated` keeps only ungated records.
- `--edge-kind` keeps records that hold an edge of that kind.
- `--linked-to <ref>` keeps records whose edges or links name the ref.
- `--forked-from <work-id>` keeps the fork children of that parent.

`list --linked-to <ref>` and `backlinks <ref>` return the same set of records.
Each `list` item adds `edges_out`, `edges_in`, `forked_from`, and `gates`.
`edges_out` items are `{kind, to}`, and `edges_in` items are `{kind, source}`.
A bad `--kind` or `--edge-kind` refuses `flag-kind`, a bad `--entry-kind` or `--entry-state` refuses `flag-entry`, and an unparseable `backlinks` ref refuses `flag-link`.

## The `pending` and `bridge` payloads

`show` and `resolve` add `pending` and `bridge` to their replies.

`pending` lists link entries first, then fork entries:

```json
[
  {"source": "wheypoint:<project_key>/<work_id>", "kind": "relates_to", "to": "wheypoint:<project_key>/<this work_id>", "revision_id": "<source revision>"},
  {"kind": "fork", "child": "wheypoint:<project_key>/<child>", "revision_id": "<child revision>",
   "moved": [{"entry_id": "<parent id>", "child_entry_id": "<child id>"}],
   "copied": [{"entry_id": "<parent id>", "child_entry_id": "<child id>"}],
   "dossier": ["<fork title>"], "links": ["<ref>"]}
]
```

`bridge` is `{state, node_ref, wheypoint_ref}`.
`resolve` reports `bridge: null` when no record resolved.

## The milknado bridge

A `checkpoints` edge to a `milknado:` ref binds the record to a Mikado goal or task.
The address a record gives milknado is `wheypoint:<project_key>/<work_id>`, never a projection path.
The bridge is data only: it reads the edge, checks for `.milknado/` at the repo root, and reports the state.

- `bound`: the record holds a `checkpoints` edge to a `milknado:` ref, and `.milknado/` exists at the repo root.
- `bridge-inactive`: the record holds that edge, but `.milknado/` is absent; the edge is inert.
- `unbound`: the record holds no `checkpoints` edge to a `milknado:` ref.

The bridge never changes `dispatchable`.
The gate mapping is data for a future milknado call:

| Wheypoint event | Milknado state |
| --- | --- |
| gated question | pending goal review |
| resolve | accepted review |
| active blocker | blocked node |
| checkpoint | snapshot receipt |

## Known costs

- Every `show`, `resolve`, `lint`, and parent `checkpoint` scans the project corpus for pending forks and links.
- `shape`, `backlinks`, and the `list` filters scan `record.json` files; no index by decision or by ref exists.
- An `xdg:` document digest changes when the document is edited, so coverage fails at the next `lint`.
