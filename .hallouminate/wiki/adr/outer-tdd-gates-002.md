# ADR: Cut owns pre-implementation RED establishment

Status: accepted (2026-08-06)

Spec: outer-tdd-gates (durable specs corpus).

## Context

Before PR #396, Cook combined failing-test creation and implementation, so the handoff into production editing lacked independently replayable evidence. Existing entry points still needed to remain usable, including direct Cook invocation.

## Decision

Add first-class `/cut` between Mold and Cook. Cut canonicalizes approved Test Contracts, adopts or writes the outer test, proves its declared pre-implementation disposition, protects the evidence files by digest, and issues the GateReceipt. Direct `/cook` synchronously invokes the same Cut preflight when no valid receipt is supplied. Adoption is allowed only when the existing test reproduces the approved failure before the first production edit. Cut never creates a red-only commit.

## Consequences

There is one producer-enforced preflight invariant regardless of entry path. Existing failing tests can be reused without duplicate tests, but only with causal reproduction evidence. Cook becomes a receipt consumer and cannot silently weaken or bypass Cut's checks.
