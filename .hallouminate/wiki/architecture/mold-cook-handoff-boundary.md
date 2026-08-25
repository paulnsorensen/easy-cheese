# Mold-to-Cook handoff boundary

Mold publishes work to Cook through a typed, route-bound pointer; Cook never executes a bare payload. The producer writes and validates immutable payload and optional normalization-receipt artifacts before atomically revealing the pointer.[^1]

## Boundary rules

- Strict typed `AgentWriterView` publication emits no normalization receipt.
- A bounded repair path may remove comments, trailing commas, single quotes, unquoted keys, uniquely implied closing delimiters, or the declared writer shorthand. Exactly one candidate must validate; semantic inference and ambiguity fail closed.[^2]
- Any repair or exact-version legacy migration emits a separate typed receipt binding the source and canonical digests.
- Publication is idempotent only when the request digest, canonical payload digest, and receipt provenance all match an existing operation.
- Cook validates the pointer contract/version, declared Mold-to-Cook route, canonical pointer metadata, referenced bytes, optional receipt binding, canonical `CurdPlan`, and every plan artifact before returning executable work.[^3]
- The legacy adapter accepts only schema version 1.0 and stops at package version 2.0.0.[^4]

These rules keep syntax recovery at the untrusted writer boundary and preserve a semantics-strict canonical contract inside the workflow.

## Verification

The conformance suite exercises an isolated bundle-only Mold publication followed by Cook acceptance with repository imports and ambient packages unavailable.[^5] Contract tests cover pointer-last interruption, retry conflicts, artifact corruption, traversal rejection, repair ambiguity, and receipt tampering.[^6]

[^1]: src/easy_cheese/shared/handoffs.py:528-675
[^2]: src/easy_cheese/shared/handoffs.py:258-464
[^3]: src/easy_cheese/shared/handoffs.py:679-729
[^4]: src/easy_cheese/shared/handoffs.py:734-769
[^5]: tests/conformance/test_replacement_stack.py:60-116
[^6]: tests/schemas/python/test_handoff_contracts.py:70-199

_Source: PR #476 implementation · Last verified: 2026-08-24_
