# Provenance and lineage

A live session can fill four optional header fields. Two note-level lineage verbs remain outside the continuity contract.

## Provenance fields

Put these optional fields before the orientation line. Only the live session supplies them. Notes without provenance remain valid.

- **`session: <harness>:<session-id>`**: Identifies an active Claude JSONL, Codex rollout, or OpenCode session. Omit it when unavailable. Claude's newest-file heuristic is `<speculative>`.
- **`git: <branch>@<short-sha>`**: Identifies the branch and short commit. Read it with `git status --short --branch` and `git rev-parse --short HEAD`. Omit it when Git inspection is unavailable or incomplete. Omit it outside a Git repository.
- **`created: <UTC ISO-8601>`**: Gives the UTC capture time.
- **`parents: [<slug>, ...]`**: Gives the lineage that the verbs below write.

## Lineage verbs

Legacy `--join` writes `parents: [<slugA>, <slugB>]`. Each `--split` child writes `parents: [<current-slug>]`. Both verbs remain outside this continuity contract. They rewrite `.cheese/notes/` Markdown and commit no delta.
