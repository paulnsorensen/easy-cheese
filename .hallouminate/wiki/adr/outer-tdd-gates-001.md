# ADR: Hybrid outside-in RED evidence uses a phase-neutral receipt

Status: accepted (2026-08-06)

Spec: outer-tdd-gates (durable specs corpus).

## Context

Before PR #396, the pipeline could hand approved behavior directly to Cook without independent executable evidence that the behavior failed before production edits. Requiring a full test matrix before every change would overbuild narrow behavioral work, while a phase-specific receipt would prevent Cut and Press from sharing one validation boundary.

## Decision

Each behavioral curd requires one tracer RED at its outermost stable public seam. A full contract matrix is required only for a ratified, versioned API, schema, or protocol. Evidence is carried by a strict phase-neutral `GateReceipt` with disposition `red` or `not-applicable` and producer `cut` or `press`; each `TestContract` retains its own tracer or matrix mode. The receipt binds the work item, witness, and protected test or fixture digests. No red-only commit is required.

## Consequences

Cook and Press can consume one typed evidence format without phase aliases. Small behavioral changes pay for one causal witness, while public contracts receive the broader matrix they need. Receipt validation becomes load-bearing and must reject inconsistent dispositions, modes, producers, witnesses, and protected-file state.
