---
slug: legacy-v013-spec-fixture
status: approved
created: 2026-05-04
confidence: high
gates_overridden: []
agent_introduced_scope: []
entity_referent_bindings: []
---

# Legacy v0.13 spec fixture

A byte-faithful v0.13-era spec: the frontmatter carries no `source` provenance
marker and no `gate_applicability` block, the Acceptance bullets carry no
`AC-N:` identifiers, and there is no `## Test Contracts` section — none of them
existed before the hardened format.

## Problem

Specs written before the hardened format still sit in `.cheese/specs/`.

## Goals

- Keep reading specs that predate the current format.

## Non-goals

- Rewriting them in place.

## Approach

Accept the legacy shape on read; mint only the hardened shape.

## Decisions

- read-side grace — rewriting a user's approved spec is not the validator's job.

## Acceptance

- WHEN the validator reads a v0.13-era spec THE SYSTEM SHALL exit 0.
- WHEN the validator mints a spec THE SYSTEM SHALL require the hardened format.

## Interface sketches

```pseudocode
validate-spec <spec-path> [--strict] -> exit 0 | exit 1 + ERROR: lines
```

## Risks

- A hardened spec that loses its provenance marker reads as legacy.

## Open questions

- [TBD] None.

## Quality gates

- `mold.pyz validate-spec <path>` exits 0 on this fixture.

## Curds

- curd-1: accept the legacy shape.

## Reproduction (Diagnose only)

Run the validator against any spec written before v0.14.

## References

None.
