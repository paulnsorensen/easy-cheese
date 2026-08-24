# ADR: Legacy handoff adapters are exact, explicit, and temporary

Status: accepted (2026-08-24)

## Decision

<certain> A legacy handoff migrates only through `contract migrate`, a provable phase route, and an adapter declared for its exact source schema and version. Migration emits a `NormalizationReceipt` and publishes a canonical pointer.[^spec]

Each adapter declares sunset metadata when introduced, remains available for at least one release, and carries tests and removal gates. Canonical acceptance does not negotiate versions or dual-write legacy forms.

## Consequences

Legacy compatibility cannot silently broaden canonical execution. Unsupported versions fail explicitly. Adapter removal is planned at introduction instead of becoming permanent compatibility surface.

[^spec]: `.cheese/specs/enforceable-skill-boundaries.md` sections Decisions, Acceptance AC-5, and Risks.
