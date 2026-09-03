## Summary

- Reconciled the manifest command surface from PRs #581 and #592.
- Rewrote all pasteurize skill prose for ASD-STE100 compliance.
- Rebuilt every skill bundle from the integrated source tree.

## Commits

- `fix(pasteurize): reconcile merged pasteurize changes`

## Source PRs

- #581
- #592

## Disagreements

none

## Outward dependencies

- `this -> shared`: `commands.py` uses `bundle_command`, `derive_command`, and `dispatch` from `shared.bundle_commands`.
- `this -> shared`: `_pasteurize_route` calls `shared.fanout.pasteurize_route_cli.main`.
- `this -> shared`: `debug_tag_sweep.py` and `repro_rerun.py` use `shared.cli`.
- `other -> this`: the build reads `src/easy_cheese/skills/pasteurize/commands.py` and emits `pasteurize.pyz`.
- These contracts did not change during reconciliation.

## STE100 status

compliant

## Follow-ups

none
