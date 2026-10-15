# ADR: Every Mold spec carries an Acceptance demonstration section

Status: accepted (2026-10-14), implemented 2026-10-15

Spec: acceptance-demonstration-press-fold (durable specs corpus).

## Context

EARS acceptance criteria and optional Test Contracts did not name the user task, a concrete input, the real boundaries, or a plausible false success. Agents spent questions on architecture instead of on the outcome the user can observe.

## Decision

The Mold spec schema (`MoldSpecDocument`) gains a required `## Acceptance demonstration` section on full specs, mini-specs, and curd mini-specs. Behavior work fills seven fields: user task, input, entrypoint, expected result, real boundaries, false success, evidence. Non-behavior work writes one `n/a: <reason>` line. Strict validation enforces it; non-strict legacy reads accept its absence.

## Consequences

One validator path covers every spec, and the opt-out stays visible. Existing strict fixtures need the section. `taste_test._draft_sections` prefix-matches headings, so it must prefer an exact `Acceptance` match or the new heading hides the acceptance criteria.
