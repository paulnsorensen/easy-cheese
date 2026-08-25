# Mold-to-Cook handoff boundary

Mold publishes work to Cook through a typed, route-bound pointer; Cook never executes a bare payload. The producer writes and validates immutable payload and optional normalization-receipt artifacts before revealing the pointer with a no-clobber commit.[^1]

## Boundary rules

- Strict typed `AgentWriterView` publication emits no normalization receipt.
- Writer text is bounded by `MAX_CONTRACT_BYTES` before repair. Standalone Markdown fences and duplicate JSON keys are rejected.[^2]
- A bounded repair path may remove comments, trailing commas, single quotes, unquoted keys, uniquely implied closing delimiters, or the declared writer shorthand. Exactly one candidate must validate; semantic inference and ambiguity fail closed.
- Any repair or exact-version legacy migration emits a separate typed receipt binding the source and canonical digests.
- Publication is idempotent only when operation ID, operation root, destination, request digest, canonical payload digest, and receipt provenance match the existing transaction.
- Duplicate plan artifact references are resolved once; distinct references still validate independently.
- Cook requires an expected operation root derived from the pointer path, validates canonical pointer bytes, and verifies every reference beneath that root before returning executable work.[^3]
- The legacy adapter accepts only schema version 1.0 and stops at canonical package version 2.0.0.[^4]

These rules keep syntax recovery at the untrusted writer boundary and preserve a semantics-strict canonical contract inside the workflow.

## Filesystem and concurrency model

Payload, receipt, and pointer files are created relative to opened directory descriptors with no-follow and no-clobber semantics. Publication binds the root and operation directories by device and inode, validates the opened directory descriptor, revalidates identities after the link, and removes a just-linked artifact if the binding changed. Losing concurrent publishers validate the winning pointer instead of overwriting it.[^5]

The pointer is the commit record and is revealed last. A symlink or parent-directory swap can therefore fail publication, but cannot leave an invalid visible pointer in the trusted operation tree.

## Verification

Contract tests cover conflicting concurrent publishers, pointer-last interruption, post-write and post-link directory swaps, symlinked retry pointers, retry conflicts, artifact corruption, traversal rejection, repair ambiguity, duplicate keys, size bounds, and receipt tampering.[^6] The staged release suite runs isolated Mold publication followed by Cook acceptance using only the staged archives.[^7]

[^1]: src/easy_cheese/shared/handoffs.py:686-832
[^2]: src/easy_cheese/shared/handoffs.py:579-630
[^3]: src/easy_cheese/shared/handoffs.py:891-949
[^4]: src/easy_cheese/shared/handoffs.py:950-983
[^5]: src/easy_cheese/shared/handoffs.py:205-377
[^6]: tests/schemas/python/test_handoff_contracts.py:133-333
[^7]: tests/python/test_stage_release.py:110-166

_Source: PR #478 review cure · Last verified: 2026-08-24_
