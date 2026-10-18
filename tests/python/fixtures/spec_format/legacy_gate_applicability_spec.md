---
slug: legacy-gate-applicability-fixture
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

# Legacy gate applicability fixture

## Problem

A spec minted before the RED gate removal still carries a removed frontmatter block.

## Goals

- Keep such a spec readable after the removal.

## Non-goals

- Exclude all other changes.

## Grounding

| Probe | Outcome | Evidence |
| --- | --- | --- |
| wiki | hit | adr/spec-format-enforcement-001.md — content-schema rules belong in the validator |
| explorer | unavailable | This fixture cannot use Hallouminate. It reads validate_spec.py directly. |

## Approach

Ignore the removed block when reading the spec.

## Decisions

- ignore-removed-block — the block no longer drives any behavior.

## Acceptance

- AC-1: WHEN the validator runs on this spec THE SYSTEM SHALL exit 0.

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

- curd-1: read the spec.
