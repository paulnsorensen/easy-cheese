# ADR: Executors consume CurdPlan and return criterion-led CurdResult

Decision status: accepted
Spec: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/workflow-contract-milknado-seam.md`

## Context

<certain> Cook and Cure currently enter through different artifacts and instructions.[^1] Milknado can map one semantic curd to several physical nodes, so node completion is not itself a semantic curd result.

## Decision

<certain> Cook and Cure are sibling executors of CurdPlan. Transport adapters resolve and validate references before calling `cook(CurdPlan)` or `cure(CurdPlan)`; there is no smaller CurdExecutionRequest.

<certain> CurdResult is criterion-led and emitted exactly once per input semantic curd. Agents report check results, deliverables, and unresolved work. The host adds identity, plan references, runtime references, and derives the result disposition.

<certain> Every input criterion has exactly one result row. Passed and failed rows require evidence. Blocked and skipped rows require a reason.

<certain> Milknado aggregates all mapped node outcomes back into one CurdResult per source curd. Unstarted nodes produce blocked criterion rows with reasons rather than missing results.

## Alternatives

- Add a shared execution-request projection: rejected because it would duplicate CurdPlan semantics.
- Return one result per physical node: rejected because semantic acceptance belongs to the source curd.
- Allow missing result rows: rejected because absence is not an observable disposition.

## Consequences

<certain> Cook, Cure, and Milknado can share the same conformance fixtures. Physical provenance remains visible without leaking scheduler fields into CurdPlan or CurdResult.

[^1]: `skills/cook/SKILL.md:44-56`; `skills/cure/SKILL.md:10-16`.
