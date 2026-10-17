# ADR: Submit snapshots and preserve revision-bound working feedback

Status: accepted design (2026-09-16); implementation pending.

## Context

Continuous co-editing adds merge and stale-answer risks.

## Decision

Autosave local edits and submit explicitly. Preserve immutable agent revisions and submitted snapshots.[^1]

## Alternatives

Live co-editing and automatic scene merges add synchronization rules that the selected workflow does not need.

## Consequences

MoldReview owns local review state. ReviewRevision owns one immutable agent document. Stale writes fail; acknowledged saves survive restart.

The user permits spec extraction with browser-test and typed-plan prerequisites still open.
This decision does not waive implementation gates or claim the feature exists.

## Related records

- [Domain model](../domain-model.md)
- [Existing-runner gate](./outer-tdd-gates-005.md)
- [Skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md)

[^1]: Approved design spec: /Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/mold-review-canvas.md; Decisions and Approved scope audit. User confirms extraction overrides on 2026-09-16.
