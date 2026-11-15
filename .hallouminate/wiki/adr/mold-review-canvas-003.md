# ADR: Embed upstream Excalidraw and retain Mermaid source

Status: accepted design (2026-09-16); implementation pending.

## Context

The user needs editable spatial diagrams and text-defined sequence diagrams.

## Decision

Embed upstream Excalidraw; reuse only audited Lavish helpers. Render Mermaid locally from editable source.[^1]

## Alternatives

Forking a drawing engine increases maintenance. Copying Lavish wholesale imports unrelated integration and server behavior.

## Consequences

Retain dependency notices and helper provenance. Do not promise automatic Excalidraw-to-Mermaid conversion.

The user permits spec extraction with browser-test and typed-plan prerequisites still open.
This decision does not waive implementation gates or claim the feature exists.

## Related records

- [Domain model](../domain-model.md)
- [Existing-runner gate](./outer-tdd-gates-005.md)
- [Skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md)

[^1]: Approved design spec: /Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/mold-review-canvas.md; Decisions and Approved scope audit. User confirms extraction overrides on 2026-09-16.
