# easy-cheese wiki — index

This wiki is the durable memory lane for the `easy-cheese` repo. It lives
at `.hallouminate/wiki/`, is **git-tracked**, and is indexed as the
`repo:easy-cheese:wiki` corpus — distinct from the per-task scratch under
`.cheese/` (corpus `cheese-local`, gitignored). Write here when a fact is
worth remembering across sessions: architecture, protocols, conventions,
and "why this design not that one" rationale.

## Topics

<!-- HALLOUMINATE:INDEX-START -->
- [architecture](./architecture.md) — skills-only collection, progressive disclosure, the cheese pipeline, portability design center.
- [tooling](./tooling.md) — `just check`/`just ci`, validators, tilth/`cheez-*` hard-fail, `.pyz` bundles, CI workflows.
- [wiki-conventions](./wiki-conventions.md) — how to author entries here, plus the durable-vs-transient boundary table.
- [workflow-invariants](./workflow-invariants.md) — pipeline ordering, two-key handshake, handoff gates, `just check` single gate.
- [spec-workflow-comparison](./spec-workflow-comparison.md) — /mold vs Matt Pocock grill-with-docs vs Superpowers brainstorming vs spec.md, plus Spec Kit/Kiro/BMAD/Taskmaster/Agent OS/OpenSpec/Tessl.
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
