# ADR-005: Size heuristics decide cook's shape

**Status:** accepted (2026-10-18; promotion line and in-flight rule 2026-10-22)

Cook has no fan-out default.
Code-computed size heuristics decide whether work cooks inline, goes to one fresh-context worker, or runs in parallel.

## Context

Fork B in the manifesto evidence (#829) asked whether cook fans out by default.
Cook fans out by default on `main` today.
PR #829 measured zero same-second parallel bursts across 609 spawns in 83 sessions.
[ADR-003](./deterministic-fanout-sizing-003.md) and [ADR-004](./deterministic-fanout-sizing-004.md) already require that code, not an agent at dispatch time, decides fan-out width.
`MAX_CURD_SURFACE` was never built.

## Decision

- Small work cooks inline when prompt caching makes that cheapest.
- One sizeable piece goes to a fresh-context worker. The spec carries its grounding plan.
- Several pieces get a parallel plan that mixes dispatched and inline work.
- A piece that is ready during molding starts at once.
- When a spec section changes under a piece in flight, the piece finishes and a follow-up piece is queued. A change in direction cancels the piece and resends it.
- Mold's full ceremony applies when a piece goes to a cold executor or changes a public contract. A fired leverage trigger still forces strong review and rules out the quick tier.

## The promotion-line conflict this resolves

On `main`, `skills/cheese/references/routing-policy.md:46` sends any fired leverage trigger to mold's full ceremony.
`skills/mold/references/tiers.md:19` lets a fired trigger enter the light or full tier.
The two rules disagree for a small, clear change that touches a trigger.
This ADR takes the tiers rule and adds the cold-executor and public-contract lines.
A fresh-context worker is a cold executor, so the size heuristic and the promotion line are one decision.

## Open design work

A follow-up `/mold` owns the details:

- the size score and its inputs;
- the grounding-plan section of the spec;
- mixed inline and dispatched pieces;
- how code or the agent detects a change in direction;
- the degrade path on a harness without sub-agents, read from the capability declaration in [codex-omp-portability-002](./codex-omp-portability-002.md).

The owner chose to make this change before a baseline measurement exists, and to correct course if it proves wrong.

## Source

Owner rulings of 2026-10-18 (fork B) and 2026-10-22 (Stream promotion line and in-flight rule), recorded in Wheypoint `tenet-reconciliation-rulings` and in #832.
