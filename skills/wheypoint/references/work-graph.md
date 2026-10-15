# The Wheypoint work graph

A record names other work and documents through typed refs and typed edges.
`fork` and `checkpoint --link` write edges; the `list` filters read them.
Each write changes only the record that starts it.

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
- A schema-3 link that holds only `path` reads as `repo:<path>` without changing stored bytes.
- A pre-v5 record loads as it is and normalizes on read; the runtime rewrites nothing.

## Edge kinds

An edge is `{to, kind, rationale?, revision_id}`, held by the record it starts from.
A record holds its edges as a set keyed by `(to, kind)`.
The host stamps `revision_id` at commit.

| Kind | Meaning |
| --- | --- |
| `forked_from` | this record is a fork child of the target |
| `supersedes` | this record replaces the target |
| `checkpoints` | this record checkpoints a Mikado goal or task |

- `forked_from` is host-only; only `fork` writes it.
- An intent or `checkpoint --link` that names `forked_from` is refused at intent validation as `invalid-intent`.
- No edge has a reciprocal; a read of the target record never shows the edge.
- Use `list --linked-to <ref>` or `list --forked-from <work-id>` to find the records on the other side.

## Links

Create a link with `checkpoint <work-id> --link <ref> --kind <edge-kind> [--covers <id>]...`.
An intent does the same with `add_edges`.
For a pinnable ref, the checkpoint also adds or refreshes the artifact link with the current digest and revision pin.
`--covers` names entry ids that the pinned link covers.
Omitting `--covers` keeps the stored coverage; `--covers` replaces it.
An intent removes an edge with `remove_edges`.

## `fork`

```bash
python3 skills/wheypoint/scripts/wheypoint.pyz fork <parent> <child> --orientation "<child title>" [--link <ref>]... [--context <path>]... [--notes-file <file>] [--next <move>] [--artifact <artifact>] [--project <key>]
```

- `fork` writes exactly one revision: the child genesis, with one `forked_from` edge.
- The edge is pinned to the parent's current revision.
- The parent record is never written by `fork`.
- The child carries no entry from the parent; copy a decision into the child notes or a link instead.
- The first line of `--orientation` becomes the child title.
- `--next` follows the same artifact rule as `checkpoint`; a missing `--artifact` for `cook` or `affinage` is refused as `invalid-intent`.
- `fork` mirrors the child projection to `.cheese/notes` and reports `repo-snapshot`, like `checkpoint`; under `--project` it writes no mirror and reports `canonical-local`.

### `fork` refusal codes

- `fork-exists`: the child work id already has a record or history.
- `unknown-parent`: the parent has no record.
- `record-unreadable`: the parent record could not be read.
- `invalid-intent`: an empty `--orientation`, a bad `--next`, or an `--artifact` that `--next` cannot use.
- `note-unwritable`: the child projection mirror could not be written.

## `list` filters

`list` adds these repeatable filters:

- `--entry-kind` and `--entry-state` keep records with a matching entry; one entry must match both.
- `--gated` keeps only gated records, and `--no-gated` keeps only ungated records.
- `--edge-kind` keeps records that hold an edge of that kind.
- `--linked-to <ref>` keeps records whose edges or links name the ref.
- `--forked-from <work-id>` keeps the fork children of that parent.
- `--owner <who>` keeps records with an active question owned by that person; the match ignores case.

Each `list` item adds `edges_out`, `edges_in`, `forked_from`, and `gates`.
`edges_out` items are `{kind, to}`, and `edges_in` items are `{kind, source}`.
A bad `--edge-kind` refuses `flag-kind`, and a bad `--entry-kind` or `--entry-state` refuses `flag-entry`.

## The `bridge` payload

`show` and `resolve` add `bridge` to their replies.
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
| checkpoint | snapshot receipt |

## Known costs

- The `list` filters scan `record.json` files; no index by decision or by ref exists.
- An `xdg:` document digest changes when the document is edited, so coverage fails at the next `resolve`.
