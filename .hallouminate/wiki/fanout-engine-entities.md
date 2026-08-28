# Fan-out engine entities

The fan-out engine (`src/fanout/`, formerly `/cheese-factory`, now driven by
`/cook`'s fan pathway — `/ultracook` is retired to a redirect stub) has three
domain entities the validators check: the **Curd**, the **Wiring node**, and
the **Curd block**. Curd and Wiring node are each *one* entity that appears at
two pipeline stages with a growing field set; each entity has a single
validation home under `src/fanout/` rather than splitting its rules across
files.

## The Curd

A Curd is the unit of independent parallel work in `/cook`'s fan pathway — one
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

## The Curd block

Added in the subagent-routing overhaul foundation (PR #315). A Curd block is
the **decomposition artifact** both decomposer doors emit -- `/mold`'s
pre-approval decomposer dispatch and `/cook`'s fallback decompose gate -- with
a **locked vocabulary that deliberately does not overlap the run-manifest
Curd**:
`curds[]` entries carry `{slug, contract, files, test_target, acceptance,
seed, est_edit_lines}` plus block-level `waves[]` and `decomposer{}`
(`src/fanout/curd_block.py`).
The disjointness of the two vocabularies is test-locked: the field-name set is
AST-derived from `curd.py`'s actual source so a collision fails the suite
(`tests/fanout/python/test_curd_block.py`).

`est_edit_lines` is a **required**, declared estimate of the curd's total
source-plus-test edit lines -- the whole dispatch's work, not just the files
it touches. `MIN_CURD_SURFACE = 25` gates it: a curd estimated below the
floor fails validation as a **merge candidate**, because a fresh coder
dispatch's context setup costs more than the edit itself. See
[ADR-004](./adr/deterministic-fanout-sizing-004.md) for why this is a
declared-and-gated estimate rather than a measurement -- at decomposition
time the diff the curd would produce does not exist yet, so it cannot be
measured the way `review_surface` measures a completed diff.

- The single producer contract lives at `skills/cheese/references/decomposer.md`
  ("same schema both doors"); the legacy `skills/ultracook/references/decomposer-prompt.md`
  produces the **incompatible run-manifest schema** and is scope-noted as
  such -- do not present the two as the same decomposer.
- Deployed as the `curd-block` subcommand of the `/cook` fan-pathway bundle (`scripts/build_pyz.py`).

## One validation home per entity

Each entity has its own module under `src/fanout/`, so "what is a valid curd"
has a single definition rather than being split across the two validators:

- `src/fanout/curd.py` — `behaviour_errors` (`curd.py:59`), `lifecycle_errors`
  (`curd.py:69`), `disjoint_files_errors` (`curd.py:90`).
- `src/fanout/wiring.py` — `graph_errors` (`wiring.py:26`), `lifecycle_errors`
  (`wiring.py:58`).
- `src/fanout/curd_block.py` — `validate_curd_block` (locked decomposition
  vocabulary; see The Curd block above).

The always-on layer is named per entity, not forced symmetric: a Curd's is
*content* (`behaviour_errors`), a Wiring node's is *graph* (`graph_errors`).
The run-manifest-only rules sit in each module's `lifecycle_errors`.
The pairwise file-disjointness **algorithm** is generalized into
`shared/scripts/schema.py::disjoint_errors` and called by both `curd.py`
(strict, `id`-keyed) and `curd_block.py` (lenient, `slug`-keyed) with each
module's original error text byte-preserved — the *invariant* stays owned per
entity, only the algorithm is shared. The parallel-eligibility gate
(`len(curds) >= PARALLEL_THRESHOLD` routes to the fan pathway; below it stays
a linear `/cook` run) stays in `validate_decomposition.py` because it is
pipeline policy, not a fact about whether a curd is valid.

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
- [age-fanout-router](./architecture/age-fanout-router.md) — deterministic review fan-out sizing (same PR).

_Source: subagent-routing-overhaul PR1 stack (PR #315 entity/validation foundation; PR #317 `/mold` integration and `/ultracook` retirement) cure/plate write-back · Updated: 2026-07-24 · Supersedes: /ultracook-owned framing (retired in PR #317)_
