# Fan-out engine entities

The `/cook` fan-out engine validates curds and wiring nodes.
Shared semantic shapes live in `src/easy_cheese_schemas/manifest.py`.
Runtime stage checks live in `src/easy_cheese/shared/fanout/`.
The retired Curd-block parser is not a third active validation home.

## The Curd

A Curd is the unit of independent parallel work in `/cook`'s fan pathway — one
behaviour, file-disjoint from its siblings. It appears at two stages:

- **Decomposition stage** — `{behavior, acceptance_criterion,
  test_target, files}`. Validated for *behavioural* invariants: a single
  verb (no "X and Y"), acceptance present, a focused single-command
  `test_target`, and file-disjointness across the curd set
  (`src/easy_cheese_schemas/manifest.py:331-345` and
  `src/easy_cheese/shared/fanout/validate_decomposition.py:60-103`).
- **Run-manifest stage** — the same curd plus `id`, `status`, and
  `retry_count`. The run requires `id >= 1`. Validated for
  *lifecycle* invariants on top of the behavioural ones
  (`src/easy_cheese/shared/fanout/curd.py::lifecycle_errors`).

So the Curd *gains* fields as it moves down the pipeline, and its
validation is layered to match: behavioural rules at every stage,
lifecycle rules only once it is in a run manifest.

## The Wiring node

A Wiring node (`W<n>`) is the unit of cross-curd integration —
`barrel_export`, `di_registration`, `route_wiring`, `event_subscription`,
`config_entry`. It has the same two-stage shape:

- **Always** — *graph* invariants: the wiring forms an acyclic DAG and
  every `depends_on` references a known id (`src/easy_cheese/shared/fanout/wiring.py::graph_errors`, called by
  `src/easy_cheese/shared/fanout/validate_decomposition.py:101`).
- **Run-manifest** — *node lifecycle*: `W<n>` id format, `type` in the
  known set, `file` present, `status` enum (`src/easy_cheese/shared/fanout/wiring.py:61-78`).

## Decomposition ownership

`DecomposedCurd` defines `behavior`, `acceptance_criterion`, `files`, and `test_target` in `src/easy_cheese_schemas/manifest.py:331-345`.
`CurdRecord` adds run-state fields such as `id`, `status`, and `retry_count`.

`src/easy_cheese/shared/fanout/validate_decomposition.py` loads each curd through the shared schema.
It checks shared-file conflicts through `reject_shared_curd_files` and wiring edges through `wiring.graph_errors`.
Its minimum-curd-count check remains pipeline policy, not a property of an individual curd.

PR #672 removes the old Curd-block parser, its dedicated test, and its `MIN_CURD_SURFACE` gate.
The former `slug`/`contract`/`est_edit_lines` shape is not the current decomposition contract.

## Validation homes

- `src/easy_cheese_schemas/manifest.py` — shared decomposition and run-state models.
- `src/easy_cheese/shared/fanout/curd.py` — content checks, run lifecycle checks, and file-disjointness helpers.
- `src/easy_cheese/shared/fanout/wiring.py` — wiring graph and lifecycle checks.
- `src/easy_cheese/shared/fanout/validate_decomposition.py` — schema-backed decomposition checks and pipeline minimum count.
- `src/easy_cheese/shared/fanout/validate_manifest.py` — run-state checks composed with decomposition, Curd, Wiring, and PR-plan validation.

`curd.disjoint_files_errors` uses `src/easy_cheese/shared/schema.py::disjoint_errors`.
The schema-backed decomposition path uses `easy_cheese_schemas.manifest.reject_shared_curd_files`.
No active caller depends on the removed Curd-block parser.

The validators remain separate entry points.
Their shared types and entity rules do not require a combined validator.

## Related

- [architecture](./architecture.md) — the skills-only collection and the cheese pipeline.
- [workflow-invariants](./workflow-invariants.md) — pipeline ordering and the curdle gate.
- [age-fanout-router](./architecture/age-fanout-router.md) — contextual
  review subject planning and workload allowances.

_Source: subagent-routing-overhaul PR1 stack (PR #315 entity/validation foundation; PR #317 `/mold` integration and `/ultracook` retirement) cure/plate write-back · Updated: 2026-09-16 · Supersedes: /ultracook-owned framing (retired in PR #317)_
