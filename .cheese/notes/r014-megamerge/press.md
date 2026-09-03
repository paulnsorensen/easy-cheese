## Summary

- Reconciled the Press command manifest and route guidance from PR #581.
- Removed repeated prose and kept one route definition for each outcome.
- Rewrote all Press skill prose for ASD-STE100 compliance.
- Rebuilt every skill bundle from the integrated source tree.

## Commits

- `feat(press): reconcile PR #581 changes`

## Source PRs

- #581

## Disagreements

none

## Outward dependencies

- `this -> shared`: `commands.py` uses `Command` and `dispatch` from `easy_cheese.shared.bundle_commands`.
- `this -> shared`: `press-route` calls `easy_cheese.shared.fanout.press_route_cli.main`.
- `this -> shared`: `press-telemetry` calls `easy_cheese.shared.fanout.press_telemetry_cli.main`.
- `this -> cook`: Press emits `Continue("press-corrective-cook")` and reads the Cook baseline contract.
- `this -> age`: Press emits `Dispatch("/age")` after a GREEN result.
- `this -> cheese`: Press uses the handback, handoff, portability, and code intelligence contracts.
- `ultracook -> this`: The no-chain directive makes Press write its handoff and stop.
- `build -> this`: The bundle build reads the Press command manifest and emits `skills/press/scripts/press.pyz`.
- PR #581 added required command summaries to the shared `Command` contract. Other listed contracts did not change.

## STE100 status

compliant

## Follow-ups

none
