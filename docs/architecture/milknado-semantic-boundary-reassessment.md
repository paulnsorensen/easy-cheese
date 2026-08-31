# Milknado Semantic Boundary Reassessment

## Decision

Keep Milknado as a consumer of `easy-cheese-schemas`. Do not move semantic
workflow models or normalization rules into Milknado.

The implementation now preserves that boundary: Easy Cheese owns contract
meaning; Milknado validates the imported projection, maps it to graph nodes,
records typed physical outcomes, and aggregates those outcomes back into
canonical `CurdResult` values.

## Deferred findings

- `workflow-contract-milknado-seam-F001` remains deferred.
- `workflow-contract-milknado-seam-F002` remains deferred.

No implementation for either finding is included in this reassessment.

## Implemented boundary

- Easy Cheese declares `easy-cheese-schemas` version `1.0.0` and excludes its
  build-time phase-registry compiler from wheels
  (`pyproject.toml:5`, `pyproject.toml:44-47`).
- Milknado declares `easy-cheese-schemas>=1.0,<2` without a local source
  override (`../milknado/pyproject.toml:20`).
- `import_milknado` validates every plan item against the immutable manifest and
  projects changes deterministically
  (`../milknado/src/milknado/domains/planning/easy_cheese.py:97-217`).
- `apply_milknado_plan_to_graph` is the graph-application boundary
  (`../milknado/src/milknado/app/easy_cheese_execution.py:24-83`).
- Physical workers deposit schema-tagged criterion outcomes; the collector
  validates node identity, ownership, source revision, batch position, and
  evidence before constructing `CurdResult`
  (`../milknado/src/milknado/app/easy_cheese_outcomes.py:22-148`,
  `../milknado/src/milknado/app/easy_cheese_bindings.py:42-164`,
  `../milknado/src/milknado/app/easy_cheese_results.py:87-249`).
- Evidence IDs are content-addressed, so a changed artifact cannot reuse a
  semantic evidence identity
  (`../milknado/src/milknado/app/easy_cheese_evidence.py:22-75`).

## Measurements

### Coupling

The Milknado production seam is 924 lines across six focused modules. Its public
surface is four operations (`import_milknado`,
`apply_milknado_plan_to_graph`, `encode_milknado_physical_outcome`, and
`collect_milknado_results`) plus immutable transport values. The implementation
does not duplicate Easy Cheese's semantic validators or normalizers.

Seventy-one focused import/conformance/result tests passed. A direct smoke run
also completed `import -> graph -> typed outcome -> CurdResult`.

### Volatility

Easy Cheese owns the version catalog, Draft 2020-12 schema generation,
migration policy, phase registry, workflow orchestration, and result
normalization. Milknado owns only physical graph/runtime state. That split keeps
semantic version changes in one package while allowing Milknado's scheduling
and persistence internals to evolve independently.

### Consumer pressure

Only the Milknado seam currently needs graph bindings. No second consumer has
demonstrated a need for Milknado's physical node or evidence types, so extracting
a third package would add a release boundary without reducing semantic coupling.

### Package and runtime footprint

The locally built `easy_cheese_schemas-1.0.0-py3-none-any.whl` is 81,549 bytes.
It contains the data-only `_compiled_phase_registry.py` and
`_schema_catalog.py`, but not `_phase_registry_compiler.py`. Cook and Cure bundle
smoke tests imported the same package from their `.pyz` artifacts
(`scripts/build_pyz.py:151-175`, `scripts/build_pyz.py:386-436`).

### Representative contract benchmark

The four-case benchmark (three first-pass-valid cases and one invalid review
repaired successfully) produced:

| Metric | Result |
| --- | ---: |
| First-pass validity | 75% |
| Repair success among attempted repairs | 100% |
| Largest canonical payload | 2,070 bytes |
| 1,000-run p95 | 1.68 ms |

These measurements are operational evidence, not release guarantees.

Those four cases now live as JSON captures in `benchmarks/contracts/`, marked
`provenance: synthetic`. `scripts/contract_benchmarks.py` replays them and
reproduces the table above; the weekly `contract-benchmarks` workflow publishes
its report to the run's job summary. The writer validity budget (under 10%
first-pass invalid) is measured over `provenance: captured` cases only, so it
reports as not measurable until real writer output is captured — that capture
path is tracked in issue #406, and the budget is deliberately not a
pull-request gate until real data shows it sustained under budget.

## Release blocker

The package boundary is implemented locally but is not yet reproducible from the
registry. The registry currently resolves only `easy-cheese-schemas==0.1.0`;
Milknado requires `>=1.0,<2`. Consequently `uv lock --check` reports that
`uv.lock` must be updated, while resolution cannot select a published compatible
version. The stale lock still records `../easy-cheese` as a directory source.

Do not restore that source override or lower the dependency range. Publish the
built `1.0.0` package through the release workflow, then refresh and verify
Milknado's lock before calling the seam releasable.

## Reconsider triggers

Reconsider a different package boundary only if at least one trigger occurs:

1. Two or more independent consumers require a stable subset of the semantic
   contracts.
2. The Milknado adapter repeatedly changes because Easy Cheese semantic models
   churn despite the major-version range.
3. The wheel or bundled runtime causes a measured startup, memory, or deployment
   regression.
4. A consumer needs a release cadence that cannot track Easy Cheese without
   compatibility shims.

Until then, one semantic owner plus a narrow physical adapter is the deeper and
less volatile design.
