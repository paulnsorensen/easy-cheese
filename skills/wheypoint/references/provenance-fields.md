# Provenance and lineage

A live session can fill four optional header fields.

Two lineage commands remain outside the continuity contract.

## Provenance fields

Put these optional fields before the orientation line.

Only the live session supplies them.

Pre-provenance notes remain valid.

- **`session: <harness>:<session-id>`** identifies an active Claude, Codex, or OpenCode session.
- Omit the field when it is unavailable.
- Claude's newest-file heuristic is `<speculative>`.
- **`git: <branch>@<short-sha>`** identifies the branch and short commit.
- Use a callable, read-only git inspection capability.
- Run `git status --short --branch` and `git rev-parse --short HEAD`.
- Omit the field when git inspection is unavailable.
- Omit the field outside a git repository.
- **`created: <UTC ISO-8601>`** gives the UTC capture time.
- **`parents: [<slug>, ...]`** gives the lineage that the commands below write.

## Record provenance

The runtime writes these fields; an intent never sets them.

- **`edges`** on the record holds its typed edges, keyed by `(to, kind)`; see [`work-graph.md`](work-graph.md).
- A fork child holds one `forked_from` edge that names the parent revision.
- A pre-v5 `origin`, `successor`, or `copies` field loads as data and stays unchanged on disk.

## Lineage commands

Legacy `--join` writes `parents: [<slugA>, <slugB>]`.

Each `--split` child writes `parents: [<current-slug>]`.

These commands remain outside this continuity contract.

They rewrite `.cheese/notes/` Markdown and commit no delta.
