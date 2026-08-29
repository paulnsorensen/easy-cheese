---
status: accepted
owner: easy-cheese
last_verified: 2026-08-29
confidence: high
---
# ADR: Legacy PrPlans are regenerated and publication receipts remain private

The PrPlan v1 cut is strict: old unversioned documents are regenerated, while Plate publication completion stays private transient state.

## Context

The hand-authored PrPlan reference schema admits `pr_number` and `pr_url`, mixing requested topology with results of publication.[^1] Plate already validates completion data through a private runtime boundary.[^2]

A compatibility layer could translate old plans, and a public receipt could formalize completion. Neither has a demonstrated durable cross-process consumer today.

## Decision

- Reject unversioned PrPlan documents after the v1 contract lands.
- Do not build a legacy adapter or migration command in this consolidation.
- Regenerate a v1 plan when resuming old transient work.
- Keep `pr_number`, `pr_url`, provider state, and landing state outside PrPlan.
- Keep Plate's existing completion receipt private and transient.
- Reconsider a public receipt only when a durable or cross-process consumer demonstrates the need.

## Alternatives

- **Ship a legacy adapter:** rejected for now because the artifacts are transient and regeneration is cheaper than permanent compatibility surface.
- **Publish a receipt contract immediately:** rejected as speculative abstraction without a second durable consumer.
- **Put result fields into PrPlan:** rejected because an immutable input plan must not become mutable publication state.

## Consequences

The implementation is smaller and the trust boundary is clearer. Old plans fail loudly instead of being interpreted heuristically. A future durable receipt will require a separate design decision rather than growing accidentally from PrPlan.

[^1]: skills/ultracook/references/pr-plan-schema.json
[^2]: src/easy_cheese/skills/plate/publication.py:59-174
