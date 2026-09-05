# Schemas reconciliation

## Summary

- The merged schemas enforce one Grounding table rule for every hardened Mold specification.
- The valid fixture and its mutation tests use clear STE100 prose.
- The rebuild updates all 13 skill bundles with the cumulative schema contracts.
- The focused schema suite passes 769 tests and skips three tests.
- The baseline consumer suite passes 10 tests.
- The full `just check` gate passes.

## Commits

- `a5d04cf` ingests the schemas slice from PR #592.
- `b649a47` ingests the schemas slice from PR #585.
- `2425592` ingests the schemas slice from PR #587.
- `ca4fe57` ingests the schemas slice from PR #588.
- `8035d9e` reconciles the combined schema behavior and rebuilds the bundles.
- `ea0ef78` refreshes the generated command references after the bundle rebuild.
- `2280bbd` rebuilds all skill bundles with the final schema contracts.
- `1c562f1` isolates the bundle build with the locked requirements.
- `8d9e677` restores the explicit baseline consumer rules and rebuilds all skill bundles.
- `a4d5611` restores merged workflow validation contracts and rebuilds all skill bundles.
- `4288e2f` synchronizes the latest Wheypoint reconciliation.
- `ac48591` restores the merged quality gates and rebuilds all skill bundles.

## Source PRs

- #585
- #587
- #588
- #592

## Disagreements

- `tests/python/test_document_rules_compiler.py` allows a hardened, not-applicable specification without Grounding rows.
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