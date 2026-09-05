# Briesearch Area Reconciliation

## Summary

The briesearch area now uses one command manifest and one validated research ledger.
The ledger supports citation checks, duplicate-call checks, call budgets, and budget extensions.
The research instructions now use one provider retrieval contract.
`just bundle` rebuilds all 13 skill bundles.
`just check` passes after the rebuild.

## Commits

- `1c8318c` ingests the PR #592 briesearch slice.
- `13d6e4e` ingests the PR #581 briesearch slice.
- `20cd72e` ingests the PR #582 briesearch slice.
- `05a39fc` reconciles the area and rebuilds the bundles.

## Source PRs

- PR #581 adds manifest-based command documentation.
- PR #582 adds citation checks and research ledger budget checks.
- PR #592 enforces the shared bundle command contract.

## Disagreements

- `src/easy_cheese/skills/briesearch/commands.py`: PR #581 adds local `_with_summary` logic. PR #592 supplies shared `derive_command` logic. The reconciliation keeps `derive_command`. This choice removes the duplicate helper and preserves required summaries.
- `skills/briesearch/SKILL.md`: one instruction requires the selected provider tool. The fallback instructions allow a compatible fetcher. The reconciliation requires an explicit fallback provider and its retrieval tool. This choice keeps fallback support and manifest verification.

## Outward dependencies

- `this -> shared`: `commands.py` imports `bundle_command`, `derive_command`, and `dispatch` from `easy_cheese.shared.bundle_commands`. The shared command contract now supplies each required summary.
- `this -> shared`: `commands.py` calls `easy_cheese.shared.artifact_path.main`. This contract does not change.
- `this -> shared`: `research_layout.py` calls `easy_cheese.shared.paths.research_layout`. PR #582 adds this layout contract.
- `this -> cheese`: `SKILL.md` uses the question, formatting, code routing, and agent resolution contracts under `skills/cheese/references`. These contracts do not change.
- `this -> age`: `SKILL.md` uses the voice and sub-agent gate contracts under `skills/age/references`. These contracts do not change.
- `this -> mold`: `synthesis.md` can select `/mold` as the next skill. The research report remains evidence, not a design decision.
- `this -> cook`: `synthesis.md` can select `/cook` as the next skill. The research report does not authorize implementation by itself.
- `build -> this`: `scripts/build_pyz.py` packages `src/easy_cheese/skills/briesearch`. The rebuilt `skills/briesearch/scripts/briesearch.pyz` contains the reconciled runtime.
- `build -> this`: `scripts/render_generated_regions.py` creates `references/commands.md` from `COMMANDS`. The generated inventory contains each required summary.

## STE100 status

compliant

## Follow-ups

none
