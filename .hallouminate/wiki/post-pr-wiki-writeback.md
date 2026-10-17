# Post-PR wiki write-back — plan and followups

The pipeline should write rationale to the wiki at two moments, and today only reliably
targets one of them. This page tracks the plan; the full design is the
`post-pr-wiki-writeback` spec (XDG corpus), and the decisions are ADRs
[[adr/post-pr-wiki-writeback-001]] and [[adr/post-pr-wiki-writeback-002]].

## The two write moments

| Moment | Skill | Writes | Status |
|---|---|---|---|
| Design time | mold curdle | design-time ADRs + domain-model merge | exists, being made **reliable** (gate node + read-back verify + completion record) |
| Post-PR | cure/ship boundary | implementation-time ADRs + domain-model deltas | **new** — dispatch `wiki-ingest` detect-and-degrade |

The post-PR step fires on every publication path (cure's terminal `/plate` dispatch,
`--open-pr`, or the orchestrator's publish phase under `ultracook`), capturing what
`/cook` and `/age` learned that curdle could not know.

## Why wiki-ingest, not wiki-curator

`wiki-ingest` (hallouminate plugin) is the portable, product-grade wiki writer.
`wiki-curator` is a personal dotfiles skill and is not portable into consumer repos — see
[[adr/post-pr-wiki-writeback-002]].

## Followups

- **hallouminate#246** — port `wiki-curator`'s authoring-hygiene capabilities
  (external-URL verify, worktree-safe write, `[[wikilink]]` convention) into `wiki-ingest`.
- **Move the trigger onto `/plate`** — `/plate`, the dedicated commit/PR skill, now exists
  (easy-cheese#272). The post-PR write-back trigger still lives at the `cure` boundary;
  move it onto `/plate` so publication and learnings-capture are wired at one seam.
