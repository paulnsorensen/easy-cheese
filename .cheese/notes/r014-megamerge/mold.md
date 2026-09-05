# Mold reconciliation result

## Summary

- This node reconciles the Mold guidance as one workflow.
- This node removes contradictory prose while preserving tested contract phrases.
- This node rewrites all Mold skill prose to comply with ASD-STE100.
- This node rebuilds all application bundles after the final source change.
- `just check` passes.

## Commits

- `699d91f` — `docs(mold): reconcile merged guidance`

## Source PRs

- PR #581
- PR #584
- PR #585
- PR #592

## Disagreements

none

## Outward dependencies

- `this -> shared`: `easy_cheese.shared.bundle_commands` provides `bundle_command`, `derive_command`, and `dispatch`.
  This contract does not change.
- `this -> shared`: `easy_cheese.shared.artifact_path`, `report_html`, `taste_test`, `publication`, and `migrate` provide Mold operations.
  The new `publish` and `migrate` commands expose the publication contracts through the Mold bundle.
- `this -> shared`: `easy_cheese.shared.document_rules` and `easy_cheese.shared.fanout.mode.PARALLEL_THRESHOLD` define validation and fan-out rules.
  These contracts do not change.
- `this -> schemas`: `easy_cheese_schemas` provides contract errors, canonical JSON, and `CURD_PLAN_SCHEMA_URI`.
  Mold now publishes typed artifacts through these contracts.
- `this -> schemas`: `easy_cheese_schemas.spec_format.spec_format_policy` validates Mold provenance and gate applicability.
  Mold now validates the required `ui_surface` field on its production path.
- `this -> cook`: Mold emits the approved spec, typed `PlannerResult`, typed `CurdPlan`, and durable handoff pointer.
  The handoff preserves applicability, contract, and taste metadata.
- `cheese -> this`: `skills/cheese/SKILL.md` routes tier-one mini-spec work to Mold.
  This route does not change.
- `this -> cheese`: `skills/cheese/references/handoff-gate.md` and `agent-resolution.md` define selection and delegate rules.
  These contracts do not change.
- `this -> briesearch`: Mold requests external evidence through `/briesearch`.
  This contract does not change.
- `culture -> this`: `/culture` can supply provenance before Mold writes a mini-spec.
  This contract does not change.
- `this -> hard-cheese`: Mold carries `--hard` to the later share-for-review gate.
  This contract does not change.
- `this -> spec-verify`: Mold can request the optional independent spec review.
  This contract does not change.
- `build -> this`: `scripts/render_generated_regions.py` reads `COMMANDS` to generate `skills/mold/references/commands.md`.
  The command inventory now includes `publish` and `migrate`.
- `build -> this`: `scripts/build_pyz.py` builds `skills/mold/scripts/mold.pyz` and the other application bundles.
  The rebuilt bundles contain the integrated command surfaces.

## STE100 status

compliant

## Follow-ups

none
