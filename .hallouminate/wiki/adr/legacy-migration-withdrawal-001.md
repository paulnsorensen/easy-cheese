# ADR: Workflow-layer CurdPlan migration is withdrawn

Status: implemented in PR #699 (2026-09-19).

No phase migrates a historical `CurdPlan` in place. Cook accepts a historical pointer only at its compatibility ingress and reports the gap as a blocked requirement.

## Context

The workflow layer carried a migration path: `src/easy_cheese/shared/migrate.py` read the adapter registry through `adapter_for` and rewrote a historical `CurdPlan` into the current contract version, and the `mold migrate` and `mold publish` commands exposed that path to users. The migration rewrote a persisted artifact on a rule that no phase owned, so an old plan could enter execution without the approval evidence that the current boundary requires. PR #699 deleted the module and both commands.

## Decision

Migration stays withdrawn. A historical `CurdPlan` pointer is accepted only at Cook's compatibility ingress, `_adopt_legacy_plan` in `src/easy_cheese/skills/cook/preparation.py`. That ingress binds the plan to a canonical spec when the caller supplies one; otherwise it returns a blocked result with a `legacy-spec-binding` requirement of kind `SCOPE`. It never rewrites the stored artifact.

The legacy adapter registry in `src/easy_cheese_schemas/compat.py` stays reference-only: no runtime consumer reads an adapter. Its sunset rule keeps a production enforcement point, because `check_adapter_sunsets` runs at the head of the same ingress. An expired adapter therefore fails the run instead of sitting registered forever.

## Alternatives

Deleting the adapter registry with its sunset machinery was proposed. The registry is kept because it records the exact-adapter and sunset rules for the next migration that needs them, and the ingress call site makes the sunset check enforceable today.

Restoring a migration command was rejected. An in-place rewrite reintroduces the unowned-rule problem that the withdrawal removed.

## Consequences

An owner of a historical plan must supply a canonical spec binding; there is no command that upgrades the artifact. Cook's blocked result names the missing binding, so the failure is legible instead of silent. `register_adapter` and `adapter_for` remain exported surface with no production caller besides the sunset check.

## Implementation status

- Deleted: `src/easy_cheese/shared/migrate.py`, the `mold migrate` and `mold publish` commands.
- Surviving ingress: `src/easy_cheese/skills/cook/preparation.py` (`_adopt_legacy_plan`, `_resolve_preparation_source`).
- Registry and sunset rule: `src/easy_cheese_schemas/compat.py` (`register_adapter`, `adapter_for`, `check_adapter_sunsets`).
- Tests: `tests/python/test_mold_cook_boundary_integration.py`, `tests/python/test_schemas_compat.py`.

## Evidence

- Review report: `.cheese/affinage/pr-699.md` (finding 44).
- Related decisions: [Legacy handoff adapters are exact, explicit, and temporary](./legacy-adapter-lifecycle-004.md), [Cook prepares missing plans but preserves plan approval](./mold-cook-boundary-001.md).
