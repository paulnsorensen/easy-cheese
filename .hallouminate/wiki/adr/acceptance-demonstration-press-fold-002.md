# ADR: Full specs and early curds carry an Acceptance demonstration section

Status: accepted (2026-10-14), implemented 2026-10-15

Spec: acceptance-demonstration-press-fold (durable specs corpus).

## Context

EARS acceptance criteria and optional Test Contracts did not name the user task, a concrete input, the real boundaries, or a plausible false success. Agents spent questions on architecture instead of on the outcome the user can observe.

## Decision

The Mold spec schema (`MoldSpecDocument`) gains an `## Acceptance demonstration` section. Strict validation requires it on full specs (Light and Full tiers) and early curd mini-specs. A Quick-tier mini-spec (`source: agent-mini-spec`) may omit it, so small work stays small; when one carries it, strict validation checks its shape. Behavior work fills seven fields: user task, input, entrypoint, expected result, real boundaries, false success, evidence. Non-behavior work writes one `n/a: <reason>` line. Non-strict legacy reads accept its absence.

## Consequences

One validator path covers every spec, and the opt-out stays visible. The tier scoping lives in `spec_format.SpecFormatPolicy.requires_section`, pinned by `tests/python/test_validate_spec.py`. Existing strict fixtures need the section. `taste_test._draft_sections` prefix-matches headings, so it must prefer an exact `Acceptance` match or the new heading hides the acceptance criteria.
