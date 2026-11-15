# ADR: Spec, Plan, and Review are separate artifact schemas

**Status:** accepted (2026-10-18; vocabulary 2026-10-22)

Spec, Plan, and Review are separate artifact schemas.
The Wheypoint record links to each one as a first-class citizen and pins the link by digest.
The record does not embed them.

## Context

Fork C in the manifesto evidence (#829) asked what the record ontology is.
OpenSpec links artifacts by `requires:` ids and spec-kit links them by path.
Both trackers name duplication and drift as their main defects, so a link needs a digest pin.
PRs #772 to #774 (merged 2026-10-15) removed the Mold-to-Cook phase contracts.
A reader who sees "Plan contract" can rebuild those phase contracts by mistake.

## Decision

Three terms keep the meaning exact:

- An **artifact schema** is the shape of a stored thing: a Spec, a Plan, or a Review.
- A **receipt** is evidence that code computes, such as a check result or a digest.
- A **gate** is a blocked transition. No gate exists between phases.

Typed exits stay at consequential boundaries.
A valid artifact schema is not proof that its content is true.

## Consequences

- The record needs an artifact-link reference with a digest pin. The `file:`, `xdg:`, `wiki:`, and `milknado:` reference schemes proposed in #829 are not on `main` as of `f45a1bc8`.
- `EdgeKind` keeps `supersedes`, so a record can state what replaced a decision and why.
- Further record cuts (fork G) wait for these links. Issue #843 tracks them.
- [workflow-contract-milknado-seam-001](./workflow-contract-milknado-seam-001.md) still holds: CurdPlan is the semantic work authority inside the Plan.

## Source

Owner rulings of 2026-10-18 (fork C) and 2026-10-22 (vocabulary), recorded in Wheypoint `tenet-reconciliation-rulings` and in #832.
