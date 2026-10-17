# Extend the canonical gateway through the remaining phases

## Outcome

Extend the approved `HandoffPointer` gateway from Cook through Press, Age, and Cure after the Mold → Cook slice lands.

## Constraints

- Preserve producer-and-consumer validation at every phase boundary.
- Accept only canonical pointers for execution.
- Keep phase payload schemas decorator-owned and transition routing registry-owned.
- Reuse pointer-last publication, receipt binding, idempotency, and corruption rejection.
- Do not broaden writer normalization or legacy adapters.

## Acceptance direction

Each new producer publishes a route-valid canonical pointer; each consumer rejects bare payloads and validates the pointer, referenced bytes, optional receipt, destination, and payload schema before execution.

## Dependency

Blocked on the `enforceable-skill-boundaries` Mold → Cook implementation stack.
