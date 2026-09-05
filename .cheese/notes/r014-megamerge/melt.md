# Melt reconciliation result

## Summary

- This node reconciles the Melt workflow as one command surface.
- This node removes contradictory file inspection guidance.
- This node rewrites all Melt reference prose to comply with ASD-STE100.
- This node rebuilds all application bundles after the final source change.
- `just check` passes.

## Commits

- `91f904a` — `docs(melt): reconcile conflict workflow`

## Source PRs

- PR #581
- PR #592

## Disagreements

- `skills/melt/SKILL.md` names `cat` and `diff`, but its I/O rule requires the selected source-code backend.
  This node keeps the backend rule because it provides one stale-safe inspection path.

## Outward dependencies

- `this -> shared`: `easy_cheese.shared.bundle_commands` provides `bundle_command`, `derive_command`, and `dispatch`.
  Melt now gives decorated callables to `derive_command` instead of module path strings.
- `this -> cheese`: `skills/cheese/references/code-intelligence-routing.md` defines the source-code backend route.
  This contract does not change.
- `this -> cheese`: `skills/cheese/references/handoff-gate.md` defines the user selection gate.
  This contract does not change.
- `build -> this`: `scripts/render_generated_regions.py` reads `COMMANDS` to generate `skills/melt/references/commands.md`.
  The manifest now derives each command from a decorated callable.
- `build -> this`: `scripts/build_pyz.py` builds `skills/melt/scripts/melt.pyz` from the Melt command surface.
  The bundle command names do not change.

## STE100 status

compliant

## Follow-ups

none
