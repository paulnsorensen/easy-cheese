# Cheese-factory pipeline entities

The `/cheese-factory` decomposition has two domain entities the validators
check: the **Curd** and the **Wiring node**. Each is *one* entity that
appears at two pipeline stages with a growing field set — and an approved
deepening (2026-06-24) gives each a single validation home under
`src/cheese-factory/` rather than splitting its rules across two files.

## The Curd

A Curd is the unit of independent parallel work in `/cheese-factory` — one
behaviour, file-disjoint from its siblings. It appears at two stages:

- **Decomposition stage** — `{id, behavior, acceptance_criterion,
  test_target, files}`. Validated for *behavioural* invariants: a single
  verb (no "X and Y"), acceptance present, a focused single-command
  `test_target`, and file-disjointness across the curd set
  (`validate_decomposition.py:28-86`).
- **Run-manifest stage** — the same curd plus runtime fields `status` and
  `retry_count`, with `id` now constrained to `int >= 1`. Validated for
  *lifecycle* invariants on top of the behavioural ones
  (`validate_manifest.py:63-97`).

So the Curd *gains* fields as it moves down the pipeline, and its
validation is layered to match: behavioural rules at every stage,
lifecycle rules only once it is in a run manifest.

## The Wiring node

A Wiring node (`W<n>`) is the unit of cross-curd integration —
`barrel_export`, `di_registration`, `route_wiring`, `event_subscription`,
`config_entry`. It has the same two-stage shape:

- **Always** — *graph* invariants: the wiring forms an acyclic DAG and
  every `depends_on` references a known id (`check_wiring_dag`,
  `validate_decomposition.py:89-133`).
- **Run-manifest** — *node lifecycle*: `W<n>` id format, `type` in the
  known set, `file` present, `status` enum (`_validate_wiring`,
  `validate_manifest.py:100-119`).

## One validation home per entity (approved, pending implementation)

Today the rules are split across two files — behavioural/graph rules in
`validate_decomposition.py`, structural/lifecycle rules in
`validate_manifest.py` — so "what is a valid curd" has no single
definition, and a run manifest validates each curd twice: an empty
`behavior` is reported by both `validate_manifest.py:90` and
`validate_decomposition.py:30`.

The approved deepening
(`.cheese/specs/cheese-factory-entity-validation.md`) gives each entity
its own module:

- `src/cheese-factory/curd.py` — `behaviour_errors`, `lifecycle_errors`,
  `disjoint_files_errors`.
- `src/cheese-factory/wiring.py` — `graph_errors`, `lifecycle_errors`.

The always-on layer is named per entity, not forced symmetric: a Curd's
is *content* (`behaviour_errors`), a Wiring node's is *graph*
(`graph_errors`). The run-manifest-only rules sit in each module's
`lifecycle_errors`. File-disjointness moves into `curd.py` as an entity
invariant; the minimum-curd-count gate (`< 5 -> /ultracook`) stays in
`validate_decomposition.py` because it is pipeline policy, not a fact
about whether a curd is valid.

**The validators are deliberately NOT merged.** `validate_decomposition.py`
and `validate_manifest.py` stay as leaf/composite validators that
*compose* the entity modules — `validate_manifest.py:17-18` already
delegates to both leaves and `pr_plan_to_branches.py:18` reuses
`validate_pr_plan`. The entities, not the validators, are the
consolidation unit. A future architecture review should not re-suggest a
four-way validator merge.

## Related

- [architecture](./architecture.md) — the skills-only collection and the cheese pipeline.
- [workflow-invariants](./workflow-invariants.md) — pipeline ordering and the curdle gate.
