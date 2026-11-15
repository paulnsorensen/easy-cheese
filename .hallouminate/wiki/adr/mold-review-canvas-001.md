# ADR: Browser choices preserve Mold authority

Status: accepted design (2026-09-16); implementation pending.

## Context

The user needs visual feedback and explicit decision capture during Mold.

## Decision

Use the browser to record choices; keep Mold as the approval and workflow authority.[^1]

## Alternatives

Feedback-only previews do not capture choices. Doing nothing retains chat-only review.

## Consequences

Stable question IDs bind answers to displayed revisions. Drawing or ordinary submission never approves a spec.

The user permits spec extraction with browser-test and typed-plan prerequisites still open.
This decision does not waive implementation gates or claim the feature exists.

## Related records

- [Domain model](../domain-model.md)
- [Existing-runner gate](./outer-tdd-gates-005.md)
- [Skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md)

[^1]: Approved design spec: /Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/mold-review-canvas.md; Decisions and Approved scope audit. User confirms extraction overrides on 2026-09-16.
