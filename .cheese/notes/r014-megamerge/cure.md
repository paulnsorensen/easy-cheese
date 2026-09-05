# Cure reconciliation

## Summary

- The Cure bundle exposes one manifest command for each shared helper.
- The merged runtime has no duplicate helper or superseded command path.
- Cure instructions now define one coherent selection, repair, review, and publication flow.
- All Cure prose uses Simplified Technical English.
- `just bundle` rebuilds all skill bundles.
- `just check` passes.

## Commits

- `db4bcae fix(cure): reconcile merged workflow contracts`

## Source PRs

- PR #581 adds the manifest command registry and generated command inventory.
- PR #592 adds the packaged Cure runtime and its enforceable phase boundary.

## Disagreements

none

## Outward dependencies

- `this -> shared`: `commands.py` calls `bundle_command`, `derive_command`, and `dispatch`.
- `this -> shared`: The manifest exposes slug, handoff, findings, gate, path, and HTML helpers.
- `this -> schemas`: Cure validates `CurdPlan` and emits one `CurdResult` for each selected curd.
- `cook -> this`: Cook provides `PlannerResult`, `CurdPlan`, baseline state, and confirmed diagnosis bindings.
- `age -> this`: Age provides findings and a locked selection.
- `this -> age`: Cure emits a handoff slug and requests `/age --scope <touched-paths>`.
- `affinage -> this`: Affinage invokes Cure with a locked selection and retains publication ownership.
- `this -> mold`: Cure reads canonical domain terms and does not reverse Mold decisions.
- `this -> plate`: Cure requests publication only after a clean result.
- `this -> hard-cheese`: Cure passes `--hard` through Plate for the metacognitive gate.
- `this -> cheese`: Cure uses shared routing, portability, handback, and handoff contracts.
- `this -> wiki-ingest`: Cure records implementation facts after publication when it owns that boundary.
- `build -> this`: The bundle builder packages Cure commands and generates `references/commands.md`.

## STE100 status

compliant

## Follow-ups

none
