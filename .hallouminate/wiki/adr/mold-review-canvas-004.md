# ADR: Use browser layouts for frontend TUI and backend reviews

Status: accepted design (2026-09-16); implementation pending.

## Context

Different subjects need different evidence layouts, not separate decision systems.

## Decision

Compose frontend, TUI, backend, and mixed layouts inside one browser application.[^1]

## Alternatives

A terminal-native reviewer creates a second interface and interaction model.

## Consequences

Layout switches retain questions, selections, and annotations. TUI review uses mockups and supplied captures, not an embedded terminal.

The user permits spec extraction with browser-test and typed-plan prerequisites still open.
This decision does not waive implementation gates or claim the feature exists.

## Related records

- [Domain model](../domain-model.md)
- [Existing-runner gate](./outer-tdd-gates-005.md)
- [Skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md)

[^1]: Approved design spec: /Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/mold-review-canvas.md; Decisions and Approved scope audit. User confirms extraction overrides on 2026-09-16.
