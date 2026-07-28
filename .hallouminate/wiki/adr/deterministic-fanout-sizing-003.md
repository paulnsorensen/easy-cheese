# ADR-003 — No LLM classifier in the sizing path

**Status:** accepted · **Spec:** `deterministic-fanout-sizing`

## Context

A glob table is a blunt instrument for "is this file part of the codebase or is
it config/generated". The obvious upgrade is a cheap explorer sub-agent that
looks at the diff and classifies files by judgment rather than pattern.

This was proposed during design and seriously considered.

## Decision

**Rejected.** Sizing stays deterministic globs.

## Why

Measured first: file classification only changes the tier of **4 of 30**
commits, each by a single rung. The upside is small and bounded.

The costs are not:

1. **It breaks the component's stated design principle.** The wiki records this
   as the defining property of the router — *"Review fan-out sizing is a
   deterministic, unit-tested routing decision, not agent judgment"*
   (`architecture/age-fanout-router.md:3-4`). With a classifier in the path, the
   same diff can size differently across runs.
2. **It cannot be regression-tested.** Every threshold in this spec was validated
   against a frozen 30-commit fixture. A judgment call in the middle of that
   pipeline makes the fixture unreproducible, which removes the evidence base the
   rest of the design rests on.
3. **It taxes the cheapest path.** The classifier would run on *every* `/age`
   invocation, including the two-line fixes that should route `n=1`. A trivial
   diff would pay for a sub-agent dispatch before learning it needs one reviewer.

## Alternative retained

Built-in defaults plus an **optional** `[review_surface]` TOML override. This
gives repos with unusual layouts an escape hatch without putting judgment in the
hot path. The failure direction is safe: an unconfigured repo over-sizes docs
PRs slightly rather than under-reviewing code.

## Scope note

This ADR governs *sizing* only. It says nothing about agent judgment inside the
review itself, which is the reviewers' entire job. The boundary is: judgment
decides **what a diff means**; deterministic code decides **how many agents look
at it**.

## Related

- [ADR-002](./deterministic-fanout-sizing-002.md) — the inverted weight table
- [age-fanout-router](../architecture/age-fanout-router.md) — the purity and determinism contract
