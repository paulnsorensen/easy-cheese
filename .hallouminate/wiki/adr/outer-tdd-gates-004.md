# ADR: Mold owns Test Contracts and a bounded fresh-context taste gate

Status: accepted (2026-08-06)

Spec: outer-tdd-gates (durable specs corpus).

## Context

Acceptance prose alone does not identify an executable seam, expected failure, or tracer-versus-matrix policy. Legacy specs cannot be abandoned, and a self-review in the authoring context is too weak to catch contract gaps reliably.

## Decision

Mold locks a Test Contract for every acceptance criterion: interface referent, outermost stable seam, failure witness, and gate mode. Legacy specs are deterministically inferred by Cut and stamped `contract_source: inferred`. Before approval, Mold runs a deterministic validator and a fresh-context taste test. The initial review may be followed by at most two corrective rounds; another failure halts approval.

## Consequences

Cut receives executable intent rather than prose interpretation. Legacy adoption is explicit and auditable. Mold gains a bounded review cost and cannot claim approval after an unbounded or author-context-only repair loop.
