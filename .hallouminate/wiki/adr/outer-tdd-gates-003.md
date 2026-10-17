# ADR: Press retains ownership of bounded corrective Cook continuations

Status: accepted (2026-08-06)

Spec: outer-tdd-gates (durable specs corpus).

## Context

Before PR #396, Press hardened the test surface after Cook and globally dispatched only to Age. A newly authored Press attack could expose an in-contract production failure, but making Press edit production or adding a global Press-to-Cook transition would blur phase ownership and disturb the existing route table.

## Decision

Press remains tests-only. When a Press-authored hardening test exposes an in-contract failure, Press emits a producer-`press` GateReceipt containing the full guard references and preserved failing-test digest, opens a fresh bounded `press-corrective-cook` continuation, and reruns the same attack when Cook returns. Press may create at most two such continuations; a third RED halts the gate. The global Press dispatch remains Age-only.

## Consequences

Production fixes stay in Cook and Press remains the owner of its hardening loop. Existing global routing semantics are unchanged. The receipt chain and continuation counter must be persisted so retries cannot reset or substitute a different witness.
