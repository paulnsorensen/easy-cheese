# Handoff preamble grammar

The shared handoff parser in `src/easy_cheese/shared/handoff.py` is the one grammar every phase emits and consumes. It accepts a small fixed preamble, one physical line per key, and it rejects or misreads anything else. The r014 skill-review round (PR #614 and the `r014-megamerge` notes) found the same defect class on almost every skill edge: a producer invented a preamble key, nested a value, or overloaded `artifact:`. This page records the grammar and the traps so a future skill edit does not repeat them. The status vocabulary and its dispositions live in [workflow-invariants](../workflow-invariants.md).

## Accepted preamble keys

The parser (`src/easy_cheese/shared/handoff.py:83-160`) requires `status`, `next`, `artifact`, and one orientation line. Only three optional keyed lines may appear before the orientation: `taste_test`, `durable_flags`, and `baseline`. The first unknown keyed line becomes the orientation text and every later line is dropped without an error. Press `action:`/`telemetry:` keys, Pasteurize `cause:`/`loop:`/`seam:` keys, and a typed Affinage `pr_ref:` key all failed this way. Put skill-specific structure in the report body, or normalize it at dispatch time; do not add a preamble key.

## `artifact:` names the consumed report

`skills/cheese/references/handback-contract.md:15-32` defines `artifact:` as the prior report the current phase consumed. Producers reused it for a PR reference, an evidence path, a spec pointer, or a richer new report, and each reuse broke Cheese resume. Keep `artifact:` for the upstream artifact and carry any other pointer in the body.

## `baseline:` is one line

The writer and parser require `baseline:` to fit one physical line (`src/easy_cheese/shared/handoff.py:166-182`); the error is "baseline must fit on one physical line". Cook's quality-gate baseline is a multi-line mapping of `{suite, test_id, signature}` records (`skills/cook/references/quality-gates.md:32-46`), so the seam carries a path to the baseline artifact, never the block. Wheypoint's typed checkpoint models omit `baseline` entirely; the [Wheypoint gotcha page](../gotchas/wheypoint-resume-traps.md) lists the dropped fields.

## `write-handoff-artifact` replaces the whole file

`src/easy_cheese/shared/write_handoff_artifact.py:106-109,164-197` writes preamble plus `--body-file` content and discards any existing file. A skill that writes its report first and then calls the writer without `--body-file` deletes its own `Applied`, `Checks`, or `Re-review` sections. Write the body to a temp file and pass `--body-file` in one step.

## The route table gates the writer

`write_handoff_artifact` calls `validate_route` from `src/easy_cheese/shared/phase_routes.py` before it writes.
`validate_route` checks `phase -> next` against the private `_ROUTES` table.
That table holds five source phases and seven routes: `age`, `cook`, `cure`, `mold`, and `press`.
The writer exits `3` for an unknown source phase or an undeclared destination.
It also exits `3` when a payload schema does not match the route, or when a transition to `done` carries a payload schema.
Two consequences follow:

- Affinage and Pasteurize are not source phases in `_ROUTES`. They cannot use the canonical writer until someone adds a route; their handoffs stay ad hoc Markdown and must still follow the key rules above.
- A same-phase loop is not expressible. `press -> press` exits `3`, and `next: press` still makes Cook's router dispatch Age. The Press corrective loop therefore stays a typed local continuation (`src/easy_cheese/shared/fanout/press_route.py`, `outcome` plus `repair_cycles` 0-2) outside the route table, per [outer-tdd-gates-003](../adr/outer-tdd-gates-003.md).

The table replaced a build-compiled registry and the per-skill `phase-contract.yaml` declarations (PR #772).
The `phase-contract` schema root is no longer published.



## Phase writes name their read revision

Since PR #776, a write to an existing Wheypoint record must pass `--base <revision_id>`, taken from the read before it.
A missing base returns `base-revision-required`, and a stale base returns `stale-parent`.
Nothing is written in either case.
A genesis and a fork child need no base.
`write-handoff-artifact --base` follows the same rule, and the earlier silent stale-parent retry is gone.
One exception keeps a lost-response retry safe: an identical phase write with its original base replays.
It exits `0` and prints the original revision with `replayed=true`.
The kernel must hold a receipt for the same request against that base.
The record must still pin the artifact to that receipt with the same bytes; see `src/easy_cheese/shared/wheypoint/phase_commit.py`.
Phase skills keep the revision from the phase-entry `resolve` as the base.
The prose contract lives in the "Base revision" section of `skills/cheese/references/handback-contract.md`.

## Findings and slug helpers

- `src/easy_cheese/shared/findings.py:40-53,108-132` requires the severity or dimension tag before any provenance tag. A reversed line parses to an empty finding list with exit `0`; nothing warns.
- `read-handoff-slug` takes `--phase <phase> --slug <slug>`; a positional path exits `2` with both flags reported missing (`src/easy_cheese/shared/read_handoff_slug.py:43-46`).
- Every phase writes its durable report to `.cheese/<skill>/<slug>.md`; Affinage uses `.cheese/affinage/pr-<n>.md`.

## Publication flags travel only in dispatch text

`--open-pr` and `--hard` have no field in any payload. They survive a chain only when each hop copies them into the next `/skill` command. `--open-pr` is publication permission: auto mode forwards it when the user supplied it and never creates it (`skills/cook/references/auto-mode.md:23-30`). `--hard` reaches Plate the same way; see [hard-cheese-gate-contract](./hard-cheese-gate-contract.md).

## Interactive gate transport

The `ask-user-question` transport (`skills/cheese/references/ask-user-question.md:6-25,95-134`) carries `id`, `prompt`, `recommended`, `multi`, and options, and returns a free-form answer as `other:<text>`. A consumer that stores a closed enum, such as Plate's `plate_layout: single | stacked`, must map `other:` text to a valid value or ask again; it must not persist the raw text.

_Source: r014 skill-review round notes (`.cheese/notes/r014-megamerge/`, ingest hash 499c49c7b67d5eb6), verified against `src/easy_cheese/shared/` on 2026-09-04 · Updated: 2026-09-04_
