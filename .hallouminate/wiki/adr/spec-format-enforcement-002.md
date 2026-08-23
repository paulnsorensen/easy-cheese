# ADR: Schema awareness via in-place generated regions; phase registry unchanged

**Status:** accepted (2026-08-23)
Spec: skills-only-spec-format-enforcement (durable specs corpus).

## Context

Agents authored spec markdown and cook writer-view JSON blind — no schema was taught at the point of instruction, and the schema entanglement (phase registry × catalog × models) was visible nowhere. BAML's prompt-embedded compact type syntax (~80% fewer tokens than JSON Schema dumps, per primary docs) is the teaching model.

## Decision

All schema projections generate at build time, drift-gated like `_schema_catalog.py`. Schema prose lands as in-place `BEGIN GENERATED` regions inside hand-authored skill references (D3): curdle.md's spec-template section and the new `skills/cook/references/writer-views.md`. The intertwine map — the join of phase registry × schema catalog × models per transition — generates wholly as `skills/cheese/references/schema-intertwine.md` under cheese's shared references. The phase-transition registry mechanism stays exactly as-is: `_require_registered_schema` (`_phase_registry_compiler.py:128`) already foreign-key-checks URIs against the catalog at compile time, so class-ref unification buys no enforcement. Cook joins `COMMON_CONSUMERS` and ships `common.pyz` (implements accepted ADR pyz-pipeline-contracts-005).

## Alternatives

- **Sidecar generated reference files (D1)** — rejected: leaves the hand-written template prose free to drift from the real rules.
- **Full template publication of skill files (D2)** — deferred (GitHub issue, follow-up F003): restructures the whole authoring/install story; revisit if generated regions proliferate.
- **Class-ref unification of the phase registry (fork B)** — deferred (GitHub issue, follow-up F002): cost across every phase-contract.yaml, no enforcement gain; the CLI seam is stringly regardless.
- **Runtime schema-dump subcommand** — rejected: no precedent in any skill ecosystem (research part 3); prompt-embedded/generated prose is the established pattern.
