# ADR: Partial plans need explicit subset approval and preserved remainder

Status: implemented for the repository boundary; external executor integration and live evidence remain (2026-09-18).

Cook may execute an explicitly approved partial plan. The unresolved remainder must remain durable, and subset success cannot complete the original task.

## Context

The planner already supports partial results with runnable curds and unresolved work. Requiring complete plans everywhere would remove useful existing behavior. Accepting only the embedded CurdPlan can instead lose the omitted work.

## Decision

Present the exact runnable subset and unresolved remainder together. Require explicit approval of that coverage. Dependencies must be closed within approved work or backed by completed prerequisite evidence.

Return a non-closed subset for replanning. Never silently expand approved scope. Changed coverage or a changed acknowledged remainder requires renewed approval.

Keep the canonical PlannerResult with subset completion records. Do not reduce continuity to the runnable plan alone.

## Alternatives

An all-or-nothing policy is simpler but blocks independent progress. The user chose bounded partial execution with explicit approval instead.

## Consequences

Partial progress remains possible without silently dropping work. Completion reporting must distinguish subset success from whole-task completion.

The versioned coverage and preparation paths now preserve partial-plan boundaries in the repository. The remaining gap is external execution/result integration and live end-to-end evidence; this ADR does not claim subset execution closes the original task.

## Implementation status

- Contract and shared validation: `src/easy_cheese_schemas/mold_cook.py` and `src/easy_cheese/shared/mold_cook_handoff.py` carry and validate exact coverage and acknowledged remainder.
- Producer: `src/easy_cheese/skills/mold/producer.py` binds the approved full or partial coverage into the finalized handoff.
- Consumer: `src/easy_cheese/skills/cook/preparation.py` validates dependency closure and preserves unresolved work as non-terminal preparation state.
- Remaining gap: external executor/result integration and its live end-to-end evidence are outside these modules.

## Evidence

- Durable spec: mold-cook-boundary, resolved through Mold artifact-path specs.
- User selected F3 option A and approved the four-curd plan for saving only.
- Existing materialization invariants: src/easy_cheese_schemas/planner.py:45-169.
- Existing partial-plan workflow tests: tests/schemas/python/test_workflow_thread.py:367-433.
- Related decision: [Plan approval remains explicit](./mold-cook-boundary-001.md).
