# Hard-cheese reconciliation

## Summary

- This node reconciles the command manifest from PR #592 with the hard-cheese runtime from PR #581.
- This node rewrites all hard-cheese markdown prose to comply with ASD-STE100.
- This node rebuilds all skill bundles once after the reconciliation.
- This node verifies the focused hard-cheese tests and the complete `just check` gate.

## Commits

- `87b61f2` — Reconciles the hard-cheese guidance and rebuilds the skill bundles.

## Source PRs

- PR #581
- PR #592

## Disagreements

none

## Outward dependencies

- `this -> shared`: `easy_cheese.shared.cli` provides CLI errors, execution, and output. This contract does not change.
- `this -> shared`: `bundle_command`, `derive_command`, and `dispatch` define the bundle command manifest. Hard-cheese now uses the decorator-based contract.
- `cheese -> this`: `skills/cheese/SKILL.md` passes `--hard` to `/plate` for the final gate. This contract does not change.
- `mold -> this`: `skills/mold/SKILL.md` passes `--hard` toward the final gate. Its boundary text now names Plate (`skills/mold/SKILL.md:121-125`).
- `cook -> this`: `skills/cook/SKILL.md` passes `--hard` through the remaining phases. This contract does not change.
- `press -> this`: `skills/press/SKILL.md` passes `--hard` to `/age`. This contract does not change.
- `age -> this`: `skills/age/SKILL.md` passes `--hard` to `/cure` and then `/plate`. This contract does not change.
- `cure -> this`: `skills/cure/SKILL.md` passes `--hard` to `/plate`. This contract does not change.
- `plate -> this`: `skills/plate/SKILL.md` calls `/hard-cheese` with the final verified artifacts. This contract does not change.
- `this -> age`: `skills/age/references/voice.md` supplies the shared result voice rules. This contract does not change.
- `this -> cheese`: `harness-portability.md` and `agent-resolution.md` supply host and judge rules. These contracts do not change.
- `build -> this`: `scripts/build_pyz.py` packages the runtime. `scripts/render_generated_regions.py` generates `references/commands.md`.

## STE100 status

compliant

## Follow-ups

none

The Mold boundary repair is complete. `skills/mold/SKILL.md:121-125` assigns
the metacognitive check to Plate.
