# ADR: Keep the local review transport bounded

Status: accepted design (2026-09-16); implementation pending.

## Context

A browser-accessible localhost server still needs an explicit access and file boundary.

## Decision

Use localhost, a launch token, host/origin checks, and declared copied assets. Expose serve, publish, poll, and close through mold.pyz.[^1]

## Alternatives

Public hosting and arbitrary workspace serving expand authentication and file-access scope.

## Consequences

Do not log tokens. Reject traversal and stale writes. Keep transport state separate from WheypointRecord and CurdPlan.

The user permits spec extraction with browser-test and typed-plan prerequisites still open.
This decision does not waive implementation gates or claim the feature exists.

## Related records

- [Domain model](../domain-model.md)
- [Existing-runner gate](./outer-tdd-gates-005.md)
- [Skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md)

[^1]: Approved design spec: /Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/mold-review-canvas.md; Decisions and Approved scope audit. User confirms extraction overrides on 2026-09-16.
