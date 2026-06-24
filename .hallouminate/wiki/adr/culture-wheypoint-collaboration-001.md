# ADR: /culture delegates its end-of-session artifact to /wheypoint

Status: accepted (2026-06-24)
Spec: culture-domain-modeling (durable specs corpus)
Design notes: .cheese/notes/culture-culture.md

## Context

`/culture` and `/wheypoint` were defined in opposition. Wheypoint's description and body explicitly excluded culture: "Do NOT use for design-only no-write reasoning notes (`/culture`)" (skills/wheypoint/SKILL.md:3,11). Culture wrote its own thin, opt-in notes slug whose `next:` value set (`mold|cook|ultracook|stop`, skills/culture/SKILL.md:62-67) had drifted behind wheypoint's richer contract, which already supports `next: culture`, `next: hold`, and `status: gated:` (skills/wheypoint/SKILL.md:32,43,48,51).

User-facing culture was being upgraded into a sustained domain-modeling partner (modeled on Matt Pocock's domain-modeling skill) whose payoff is a durable, resumable document, not just conversation. That reframes a culture session as legitimately checkpoint-worthy, which is exactly what wheypoint produces.

## Decision

User-facing `/culture` sessions end by invoking `/wheypoint` to write the durable handoff, rather than writing a culture-specific thin slug. Wheypoint's carve-out excluding culture is removed; culture becomes a named, legitimate caller. Culture stops documenting its own slug schema and references wheypoint's as the single source of truth.

This couples the two skills: wheypoint now owns the compaction, redaction, state-map, and resume contract for culture's artifact, eliminating a duplicated and already-stale schema.

## Why not the alternatives

- Inline wheypoint-grade richness into culture: keeps wheypoint pristine but duplicates the full compaction and redaction logic across two skills, with drift risk (the stale thin schema is evidence this already happened).
- Leave culture as-is: the felt gap (shallow investigation, forced convergence, awkward handoff gate) remains; the durable-doc payoff never materializes.

## Scope guard

The change applies to user-facing mode only. Internal mode (the silent reasoning pass every workflow skill and `/cheese` step-1 invoke) stays silent, light, and no-writes, and inherits none of the buffs. This guard is what keeps the coupling safe: only the human-driven, opt-out-of-writes path produces a wheypoint.
