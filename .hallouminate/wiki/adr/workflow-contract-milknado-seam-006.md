# ADR: Easy Cheese proves the core seam before Milknado adoption

Decision status: accepted
Spec: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/workflow-contract-milknado-seam.md`

## Context

<certain> Milknado does not currently depend on easy-cheese-schemas and already owns its batch and execution model.[^1] Importing an unproven semantic package first would make Milknado the place where Easy Cheese contract defects are discovered and repaired.

## Decision

<certain> Implementation order is: contracts and executable schemas; Easy Cheese Mold-to-Planner-to-Cook steel thread; compiled transition registry and package fixtures; package publication; Milknado dependency and CurdPlan import; plan-v2 projection; CurdResult aggregation; shared conformance; boundary reassessment.

<certain> Milknado owns batches, waves, estimates, retries, worktrees, executor selection, and runtime policy. CurdPlan owns semantic work and verification.

<certain> The importer and aggregation proof must preserve `source_plan_ref` and `source_curd_ref` and run the exact published Easy Cheese fixture corpus.

<certain> After the proof, a tracked reassessment records importer friction and either preserves or evidence-adjusts the boundary. Wider Easy Cheese adoption remains F001; generic execution continuity remains F002.

## Alternatives

- Adopt in Milknado before an Easy Cheese producer and consumer: rejected because no local steel thread would prove the contract.
- Migrate every Easy Cheese skill first: rejected because importer friction should inform the wider rollout.
- Specify Milknado scheduler policy here: rejected because it belongs to Milknado.

## Consequences

<certain> The cross-repository seam becomes an explicit conformance gate instead of an assumption. The package release version remains a publication-time mechanical decision.

[^1]: `/home/paul/Dev/milknado/pyproject.toml:5-24`; `/home/paul/Dev/milknado/src/milknado/domains/batching/change.py:32-40,74-77`.
