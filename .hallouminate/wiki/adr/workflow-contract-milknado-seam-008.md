# ADR: milknado is an optional plugin coupled by artifact pointers

**Status:** accepted (2026-10-18)
**Supersedes in part:** [workflow-contract-milknado-seam-006](./workflow-contract-milknado-seam-006.md), the steps that add a milknado dependency on easy-cheese schemas and import CurdPlan at runtime.

milknado stays the parallel executor.
Easy-cheese consumes it as an optional plugin.
The two projects couple at the artifact boundary by pointer, with no runtime import.

## Context

Fork J in the manifesto evidence (#829) asked whether to execute Shape B (runtime import, decided 2026-08-28) or keep pointer coupling.
Shape B was never executed.
milknado's own `docs/adr/adversarial-review-loops-003.md` (accepted 2026-07-19) integrates at the artifact and format layer with no runtime coupling.
milknado's dependency list has no easy-cheese entry.

## Decision

- milknado is optional. Every easy-cheese workflow runs without it and states any lost capability.
- Easy-cheese and milknado exchange artifacts by pointer, such as a Plan reference with a digest.
- Neither project imports the other's runtime package.

## Consequences

- `docs/architecture/milknado-semantic-boundary-reassessment.md` still describes milknado as a consumer of `easy-cheese-schemas`. That page needs reconciling with this ADR.
- The parallel plans in [deterministic-fanout-sizing-005](./deterministic-fanout-sizing-005.md) run on cook's own dispatch when milknado is absent.

## Source

Owner ruling of 2026-10-18 (fork J), recorded in #832 and Wheypoint `tenet-reconciliation-rulings`.
