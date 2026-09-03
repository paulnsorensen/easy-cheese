# Provenance and lineage

A live session can fill four optional header fields. Two lineage commands remain outside the continuity contract.

## Provenance fields

Put these optional fields before the orientation line. Only the live session supplies them. Pre-provenance notes remain valid.

- **`session: <harness>:<session-id>`**: Identifies an active Claude JSONL, Codex rollout, or OpenCode session. Omit the field when unavailable. Claude's newest-file heuristic is `<speculative>`.
- **`git: <branch>@<short-sha>`**: Identifies the branch and short commit. Use a callable, read-only git inspection capability. Run `git status --short --branch` and `git rev-parse --short HEAD`. Omit the field when git inspection is unavailable. Omit the field outside a Git repository.
- **`created: <UTC ISO-8601>`**: Gives the UTC capture time.
- **`parents: [<slug>, ...]`**: Gives the lineage that the commands below write.

## Lineage commands

Legacy `--join` writes `parents: [<slugA>, <slugB>]`. Each `--split` child writes `parents: [<current-slug>]`. These commands remain outside this continuity contract. They rewrite `.cheese/notes/` Markdown and commit no delta.
