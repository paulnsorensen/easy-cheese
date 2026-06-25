# easy-cheese wiki — index

This wiki is the **git-tracked** durable memory lane for the
`easy-cheese` repo. It lives at `.hallouminate/wiki/` and is indexed as
the `repo:easy-cheese:wiki` corpus. Write here when a fact is worth
remembering across sessions: architecture, protocols, conventions, and
"why this design not that one" rationale. Two sibling lanes hold the
rest: durable specs and research reports live out of git at the XDG
project corpus (`$XDG_DATA_HOME/cheese/<project>/`), and transient
per-task scratch stays gitignored under `.cheese/`. Durability is not the
git-tracking axis (`shared/formatting.md:103`).

## Topics

<!-- HALLOUMINATE:INDEX-START -->
- [adr/](./adr/index.md) — adr
- [architecture](./architecture.md) — Architecture of easy-cheese
- [cheese-factory-entities](./cheese-factory-entities.md) — Cheese-factory pipeline entities
- [skill-parity-analysis](./skill-parity-analysis.md) — Skill-parity analysis
- [tooling](./tooling.md) — Tooling
- [wiki-conventions](./wiki-conventions.md) — Wiki conventions for easy-cheese
- [workflow-invariants](./workflow-invariants.md) — Workflow invariants
<!-- HALLOUMINATE:INDEX-END -->

## How to use this index

`index.md` is a table of contents, not a topic. New pages join the list
above with a one-line gloss; anything substantive belongs in its own
topic file. The daemon rewrites the link list between the
`HALLOUMINATE:INDEX` markers after every `add_markdown` — curated prose
outside the markers is preserved.

If the index looks stale, run `list_files` against the
`repo:easy-cheese:wiki` corpus — the directory is the source of truth.
Start with [wiki-conventions](./wiki-conventions.md) before writing your
first entry.
