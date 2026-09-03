# Schemas reconciliation

## Summary

- The merged schemas enforce one Grounding table rule for every hardened Mold specification.
- The valid fixture and its mutation tests use clear STE100 prose.
- The rebuild updated all 13 skill bundles with the cumulative schema contracts.
- The focused schema suite passed 769 tests and skipped three tests.
- The baseline consumer suite passed 10 tests.
- The full `just check` gate passed.

## Commits

- `a5d04cf` ingested the schemas slice from PR #592.
- `b649a47` ingested the schemas slice from PR #585.
- `2425592` ingested the schemas slice from PR #587.
- `ca4fe57` ingested the schemas slice from PR #588.
- `8035d9e` reconciled the combined schema behavior and rebuilt the bundles.
- `ea0ef78` refreshed the generated command references after the bundle rebuild.
- `2280bbd` rebuilt all skill bundles with the final schema contracts.
- `1c562f1` isolated the bundle build with the locked requirements.
- `8d9e677` restored the explicit baseline consumer rules and rebuilt all skill bundles.
- `a4d5611` restored merged workflow validation contracts and rebuilt all skill bundles.
- `4288e2f` synchronized the latest Wheypoint reconciliation.
- `ac48591` restored the merged quality gates and rebuilt all skill bundles.

## Source PRs

- #585
- #587
- #588
- #592

## Disagreements

- `tests/python/test_document_rules_compiler.py` allowed a hardened, not-applicable specification without Grounding rows.
  PR #585 requires both probes for every hardened specification.
  The reconciliation keeps the PR #585 rule because it records the required evidence.
- `src/easy_cheese/skills/wheypoint/commands.py` declared `checkpoint` separately from the decorated command manifest.
  The merged command validator requires one declaration mechanism.
  The reconciliation keeps the decorated manifest because it removes the duplicate declaration path.

## Outward dependencies

- `this -> shared`: The schemas emit `NormalizationReceipt`, `HandoffPointer`, and legacy adapter contracts.
- `shared -> this`: `src/easy_cheese/shared/migrate.py` imports the adapter registry and normalization contracts.
- `shared -> this`: `src/easy_cheese/shared/publication.py` imports the handoff and normalization contracts.
- `this -> mold`: The schemas emit `MoldSpecDocument`, `GroundingProbe`, and `GroundingOutcome`.
- `mold -> this`: `src/easy_cheese/skills/mold/validate_spec.py` validates specifications with those contracts.
- `this -> wheypoint`: The schemas emit `WheypointDelta.compaction` and `WheypointRevision.compaction`.
- `wheypoint -> this`: The Wheypoint runtime consumes the compaction and lineage contracts.
- `build -> this`: `scripts/build_pyz.py` compiles the schema catalog into each skill bundle.
- `build -> this`: `scripts/render_generated_regions.py` reads registered contracts and writer payload types.
- `build -> this`: `scripts/check_bundles.py` loads the declared runtime and build requirements before each isolated rebuild.
- `this -> build`: `justfile` resolves schema runtime dependencies before `scripts/build_pyz.py` compiles the catalog.

## STE100 status

compliant

## Follow-ups

none