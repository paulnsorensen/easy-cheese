# Fan-out engine entities

The fan-out engine (`src/fanout/`, formerly `/cheese-factory`, now driven by
`/ultracook`'s parallel mode) has two domain entities the validators check:
the **Curd** and the **Wiring node**. Each is *one* entity that appears at two
pipeline stages with a growing field set, and each has a single validation
home under `src/fanout/` rather than splitting its rules across two files.

## The Curd

A Curd is the unit of independent parallel work in `/ultracook` parallel mode — one
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

## One validation home per entity

Each entity has its own module under `src/fanout/`, so "what is a valid curd"
has a single definition rather than being split across the two validators:

- `src/fanout/curd.py` — `behaviour_errors` (`curd.py:59`), `lifecycle_errors`
  (`curd.py:69`), `disjoint_files_errors` (`curd.py:90`).
- `src/fanout/wiring.py` — `graph_errors` (`wiring.py:25`), `lifecycle_errors`
  (`wiring.py:72`).

The always-on layer is named per entity, not forced symmetric: a Curd's is
*content* (`behaviour_errors`), a Wiring node's is *graph* (`graph_errors`).
The run-manifest-only rules sit in each module's `lifecycle_errors`.
File-disjointness lives in `curd.py` as an entity invariant; the parallel-
eligibility gate (`len(curds) >= PARALLEL_THRESHOLD` routes to parallel mode;
below it stays linear `/ultracook`) stays in `validate_decomposition.py`
because it is pipeline policy, not a fact about whether a curd is valid.

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
