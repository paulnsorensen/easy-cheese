---
slug: behavior-mini-spec
source: agent-mini-spec
intent: Add an observable behavior.
blast_radius: low
inputs: A valid request.
outputs: A validated response.
gate_applicability:
  disposition: red-required
  work_class: behavior
  ui_surface: non-browser
verification: Run the focused behavior test.
---

## Contract

Add one observable behavior at the existing public interface.

## Acceptance

- AC-1: WHEN a valid request arrives THE SYSTEM SHALL return the validated response.

## Test Contracts

| Acceptance ID | Interface referent | Outermost stable seam | Expected failure | Mode | Interface version | Matrix rows |
| --- | --- | --- | --- | --- | --- | --- |
| AC-1 | public request interface | integration test at the public API | response validation fails | tracer | | |

## Non-goals

- New interfaces.
