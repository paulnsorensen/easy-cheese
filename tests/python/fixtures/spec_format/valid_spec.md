---
slug: valid-spec-format-fixture
status: approved
source: mold-handshake
created: 2026-08-23
confidence: high
gates_overridden: []
agent_introduced_scope: []
gate_applicability:
  disposition: red-required
  work_class: behavior
  ui_surface: non-browser
---

# Valid spec format fixture

## Problem

The current spec format permits invalid documents. Add a mechanical check.

## Goals

- Enforce the spec format at curdle time.

## Non-goals

- Exclude all other changes.

## Grounding

| Probe | Outcome | Evidence |
| --- | --- | --- |
| wiki | hit | adr/spec-format-enforcement-001.md — content-schema rules belong in the validator |
| explorer | unavailable | This fixture cannot use Hallouminate. It reads validate_spec.py directly. |

## Approach

Hand-roll a validator that consumes the generated document rules.

## Decisions

- hand-rolled-validator — no maintained tool covers content-schema rules.

## Acceptance

- AC-1: WHEN the validator runs on a valid tracer spec THE SYSTEM SHALL exit 0.
- AC-2: WHEN the validator runs on a valid contract-matrix spec THE SYSTEM SHALL exit 0.

## Test Contracts

| Acceptance ID | Interface referent | Outermost stable seam | Expected failure | Mode | Interface version | Matrix rows |
| --- | --- | --- | --- | --- | --- | --- |
| AC-1 | validate-spec CLI | pytest calls the CLI as a subprocess | no validator exists yet | tracer | | |
| AC-2 | validate-spec CLI | pytest calls the CLI as a subprocess | no validator exists yet | contract-matrix | v1 | row-a, row-b |

## Interface sketches

```pseudocode
validate-spec <spec-path> -> exit 0 | exit 1 + ERROR: lines
```

## Risks

- No other validator drift risks apply.

## Open questions

- There are no open questions.

## Quality gates

- `python3 src/easy_cheese/skills/mold/validate_spec.py <path>` exits 0 on this fixture.

## Curds

- curd-1: build the validator.
