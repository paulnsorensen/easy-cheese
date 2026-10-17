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

The change applies to user-facing mode only. Internal mode (the silent reasoning pass every workflow skill and `/cheese` step-1 invoke) stays silent, light, and no-writes, and inherits none of the buffs. This guard is what keeps the coupling safe: only the human-driven user-facing path produces a wheypoint. That path covers explicit no-write requests and explicit requests to think through a problem (for example, "these bugs feel connected"). Fix and diagnose requests stay on `/pasteurize`.

## Problem-altitude prototype

Culture uses intent-driven altitude navigation in ordinary user-facing conversation, without a required mode flag or exact keyword.[^altitudes]
The user approves this direction for the prototype; publication remains under review.
Conversational cues such as “zoom out” and “make that concrete” are examples, not reserved commands.
Culture combines problem level, evidence source, and thinking move instead of selecting an exclusive mode.[^altitudes]

Culture suggests a useful change of altitude when evidence indicates a pattern or a gap between behavior and goals.
It states its interpretation and stays within the agreed evidence scope.
A suggestion does not authorize a full audit, project mutation, or a move to Mold.
Simple local questions do not require a full altitude tour, table, or diagram.[^altitudes]

Problem framing reuses Culture's record ledger and Wheypoint session handoff.
The problem brief travels through that handoff; it does not introduce another artifact schema.
Silent internal mode stays light and unchanged.
Mold receives the user's selected problem and unresolved hypotheses, not an approved implementation.[^handoff]

[^altitudes]: skills/culture/SKILL.md:19-29; skills/culture/references/problem-altitudes.md:14-61
[^handoff]: skills/culture/references/problem-altitudes.md:131-150

_Source: User-approved Culture navigation revision · Updated: 2026-10-15 · Supersedes: explicit `--altitudes` prototype selection · 2026-10-14_
