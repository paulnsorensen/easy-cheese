# Cook reconciliation

## Summary

- The Cook bundle now exposes the manifest command set and the canonical `accept` command.
- The command wrappers map each command to one implementation.
- No duplicate helper or superseded path remains.
- All Cook prose uses Simplified Technical English.
- `just bundle` rebuilt all skill bundles.
- `just check` passed.

## Commits

- `62b12ec fix(cook): reconcile merged workflow contracts`

## Source PRs

- PR #581 adds the manifest command registry and generated command inventory.
- PR #586 aligns the Cook instructions with the review workflow and Simplified Technical English.
- PR #592 adds canonical acceptance for a Mold `HandoffPointer`.

## Disagreements

none

## Outward dependencies

- `this -> shared`: `commands.py` calls bundle dispatch, artifact, fan-out, worktree, handoff, report, and path helpers.
- `this -> shared`: `contract_handlers.py` calls `publication.accept` and handles `PublicationError`.
- `this -> schemas`: contract handlers use `CurdPlan`, validation, canonical serialization, digests, and transition errors.
- `mold -> this`: Mold emits the canonical `HandoffPointer` that Cook accepts.
- `this -> mold`: Cook emits `PlannerRequest` for planning and routes specification failures to Mold.
- `this -> press`: Cook emits behavior handoffs and accepts correction-loop results.
- `this -> age`: Cook requests curd reviews, taste tests, and the final review.
- `this -> cure`: Cook sends confirmed diagnosis bindings and receives repaired curd results.
- `this -> plate`: Cook requests topology preflight and carries `--open-pr` publication intent.
- `this -> pasteurize`: The quality-gate policy can dispatch an isolated repair for recorded debt.
- `this -> cheese`: Cook uses the shared handoff gate and the `/cheese --continue` resume route.
- `build -> this`: The bundle builder packages Cook commands and generates `references/commands.md`.

## STE100 status

compliant

## Follow-ups

none
