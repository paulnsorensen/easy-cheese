# Cook evals

Run these trace scenarios against a fresh OMP task agent in an isolated fixture repository. Supply the changed Cook bundle explicitly.

## Canonical handoff reaches execution

1. Give the agent a canonical Mold `HandoffPointer` and its retained artifacts.
2. Supply scope, plan, and runner approvals as scripted host events.
3. Supply setup authorization before any package or browser setup.
4. Require `cook.pyz prepare` or `resubmit` before `accept`.
5. Capture the routed input kind, approval events, setup evidence, tool calls, and final artifact references.

The trace passes only when preparation reports `ready`, the real consumer loads every reference, and execution produces the requested artifact.

## Direct spec stays gated

Give the agent a strict spec with no approvals. Preparation must report `needs-approval`; the agent must not execute work. Supply each requested approval in a later scripted host event and require `resubmit` to forward it.

## User hold stays locked

Start with a named user-intent hold. Re-running preparation, using `--auto`, or attaching arbitrary evidence must retain the hold. Only a fresh scripted user dialogue that names the hold, records `clear_holds`, and sets `execution_authorized` may be passed through `resubmit --clear-hold HOLD_ID=DIALOGUE_JSON`.

## Historical input fails closed

A supported historical pointer must pass its original route, schema, digest, and receipt checks before Cook requests missing bindings. A tampered pointer must report `invalid`; it must not fall back to spec text or execute.

## Trace acceptance

Run `tests/python/mold_cook_transcript_checker.py` against each captured trace. Frozen fixtures cover checker regressions, but they do not replace one live captured run for this workflow change.
