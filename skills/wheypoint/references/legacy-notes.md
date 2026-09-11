# Legacy notes

## Handwritten legacy notes

A handwritten note under `.cheese/notes/` predates the continuity kernel.

The `resolve` command still reads it, and a legacy result is never authoritative.

A legacy result gates a resume for a human decision.

## Header keys

A legacy note accepts `mode:`, `order:`, `session:`, `git:`, `created:`, `parents:`, and `baseline:` between `artifact:` and the orientation.

`mode:` is optional; an omitted mode means `mode: single`.

In `mode: single`, `next:` names the skill that the new agent runs.

For multiple read-only moves, use a `next:` list with `order: parallel | sequential`.

Use only `briesearch` or `culture` in an inline `next:` list.

See [`provenance-fields.md`](provenance-fields.md) for `session:`, `git:`, `created:`, and `parents:`.

## Legacy status values

- `halt: <one-line reason>` is valid only in a handwritten note.
- The runtime never derives `halt`; derived status has only `ok` and `gated:`.
- `resolve` gates every legacy status whose disposition is not `proceed`.
- A legacy `halt` therefore stops: the reader shows the reason and dispatches nothing.

## Baseline

A handwritten note can record a one-line `baseline:` value.

The baseline is settled state; do not re-ask, re-flag, or re-halt on identical baseline entries.

The canonical record carries no baseline field, so keep a Cook baseline mapping in the Cook handoff.

See [`../../cook/references/quality-gates.md`](../../cook/references/quality-gates.md).

## Resume semantics

`/cheese --continue <slug>` resolves the slug through `resolve` and dispatches `next:` only from a validated current revision.

An absolute note path resolves as an explicit path first.

Resume preserves `mode:`, `--hard`, `--open-pr`, `--safe`, and an explicit `--auto`.

Press corrective work remains `continue: press-corrective-cook`, not a global Press-to-Cook dispatch.
