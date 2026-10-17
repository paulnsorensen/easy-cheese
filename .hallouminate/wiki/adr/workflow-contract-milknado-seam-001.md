# ADR: CurdPlan is the semantic work authority

Decision status: accepted
Spec: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/workflow-contract-milknado-seam.md`

## Context

<certain> Easy Cheese currently carries three overlapping shapes: CurdBlock for pre-run fan-out, Decomposition for legacy planning, and CurdRecord for mutable runtime dispatch state.[^1] Milknado separately owns its physical batch plan.[^2]

Treating any physical shape as canonical would force semantic checks, scheduler layout, and runtime state into one contract.

## Decision

<certain> CurdPlan is the sole semantic authority. It owns outcomes, bounded scope, inputs, outputs, dependencies, checks, and optional shared inputs, constraints, and invariants.

<certain> CurdBlock and Decomposition remain lossless-only projections. A projection that cannot represent every semantic field returns UnsupportedProjection with curd and field details. It never flattens or expands a legacy type into a second semantic authority.

<certain> CurdRecord retains runtime state and its existing integer dispatch `id`. Semantic `curd_id` is a separate opaque identity.

<certain> Milknado plan v2 remains a physical projection carrying `source_plan_ref` and `source_curd_ref`.

## Alternatives

- Make CurdBlock canonical: rejected because waves and estimates are physical planning data.
- Make Decomposition canonical: rejected because its single criterion and test target cannot express the approved semantic model.
- Expand both legacy types: rejected because two evolving authorities would drift.

## Consequences

<certain> Cook, Cure, and Milknado share one semantic input while retaining different execution machinery. Legacy conversion becomes explicitly fallible, and F001 owns eventual retirement.

[^1]: `src/easy_cheese_schemas/curd.py:132-148`; `src/easy_cheese_schemas/decomposition.py:39-43`; `src/easy_cheese_schemas/manifest.py:328-358`.
[^2]: `/home/paul/Dev/milknado/src/milknado/domains/batching/change.py:32-40,74-77`.
