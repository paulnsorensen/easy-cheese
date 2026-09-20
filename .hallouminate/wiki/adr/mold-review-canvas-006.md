# ADR: Review artifacts without executing supplied programs

Status: accepted design (2026-09-16); implementation pending.

## Context

Interactive application previews expand execution and process-management scope.

## Decision

Support editable review artifacts without launching project apps or executing supplied scripts or terminal programs.[^1]

## Alternatives

Executing live prototypes provides behavior review but needs a separate isolation and lifecycle design.

## Consequences

The canvas itself remains interactive. Imported executable content is rejected or displayed without execution.

The user permits spec extraction with browser-test and typed-plan prerequisites still open.
This decision does not waive implementation gates or claim the feature exists.

## Related records

- [Domain model](../domain-model.md)
- [Existing-runner gate](./outer-tdd-gates-005.md)
- [Skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md)

[^1]: Approved design spec: /Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/mold-review-canvas.md; Decisions and Approved scope audit. User confirms extraction overrides on 2026-09-16.
