# ADR: Curdle overrides save work without granting execution

Status: implemented for the repository boundary; external runner integration and live evidence remain (2026-09-18).

The curdle anyway behavior saves a non-ready design. It never waives required execution-readiness checks.

## Context

The old override wording allowed one extraction despite failed coherence checks. The repository boundary now records machine-readable non-ready requirements; Issue 694 was the false-ready failure that motivated this decision.

## Decision

Save the incomplete design with explicit unmet requirements. Do not publish a ready pointer or emit an automatic execution hint. Cook may later complete authorized preparation.

An explicit do-not-implement instruction is a separate hold. Neither saving nor preparation clears that hold.

Document lifecycle, output readiness, handback status, and Wheypoint status remain distinct concepts.

## Alternatives

A closed list of readiness waivers could allow selected incomplete designs to execute. The user instead chose save-only authority to keep the override from bypassing readiness.

## Consequences

Incomplete work remains durable without false permission to execute. Sizing becomes advisory; finalization owns ready-handoff recommendations.

The producer and consumer paths now keep incomplete designs non-ready and record their unmet requirements. The remaining gap is external runner/setup evidence and live end-to-end exercise; this ADR does not claim those are supplied by the schema alone.

## Implementation status

- Contract and shared validation: `src/easy_cheese_schemas/mold_cook.py` and `src/easy_cheese/shared/mold_cook_handoff.py` carry and validate readiness evidence and hold state.
- Producer: `src/easy_cheese/skills/mold/producer.py` translates missing readiness into a non-ready result and reveals a pointer only for a ready handoff.
- Consumer: `src/easy_cheese/skills/cook/preparation.py` keeps saved requirements and holds separate from execution authority until the accepted evidence is complete.
- Remaining gap: external runner/setup integration and its live end-to-end evidence are outside these modules.

## Evidence

- Durable spec: mold-cook-boundary, resolved through Mold artifact-path specs.
- User selected F2 option A and approved the design for saving only.
- Existing override: skills/mold/references/handshake.md:163-165.
- Existing advisory routing behavior: `_recommend` and `analyze` in src/easy_cheese/skills/mold/curd_count.py.
- Related decision: [Plan approval remains explicit](./mold-cook-boundary-001.md).
