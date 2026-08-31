# Provenance and lineage

The four optional header fields the live session fills in, and the two note-level lineage verbs that sit outside the continuity contract.

### Provenance fields

These optional fields precede the orientation line and come only from the live session; pre-provenance notes remain valid.

- **`session: <harness>:<session-id>`** — active Claude JSONL id, Codex rollout id, or OpenCode session row. Omit when unavailable; Claude's newest-mtime heuristic is `<speculative>`.
- **`git: <branch>@<short-sha>`** — branch and short commit from a callable, read-only git inspection capability (`git status --short --branch`; `git rev-parse --short HEAD`). Omit the field when git inspection is unavailable, outside git, or incomplete.
- **`created: <UTC ISO-8601>`** — UTC capture time.
- **`parents: [<slug>, ...]`** — lineage, written by the verbs below.

### Lineage verbs

Legacy `--join` writes `parents: [<slugA>, <slugB>]`; `--split` children write `parents: [<current-slug>]`. Both remain outside this continuity contract: they rewrite `.cheese/notes/` Markdown and commit no delta.
