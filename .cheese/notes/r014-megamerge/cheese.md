# Cheese area reconciliation

## Summary

- This node reconciles routing receipts, continuation, regrounding, and generated schema guidance.
- This node removes duplicate routing instructions and keeps each detailed contract in its reference file.
- This node rebuilds all shipped Python bundles after the integrated changes.

## Commits

- `554fafb2` ingests the cheese slice from PR #592.
- `58f01485` ingests the cheese slice from PR #583.
- `6e537c09` ingests the cheese slice from PR #589.
- `a3afd0d` reconciles the cheese area and rebuilds the bundles.

## Source PRs

- #583
- #589
- #592

## Disagreements

- `skills/cheese/SKILL.md`: PR #583 propagates `--auto` broadly, while PR #589 makes continuation opt-in. The integration keeps opt-in continuation because the validated handoff controls resume behavior.
- `skills/cheese/references/classification.md`: the older router dispatches retired `/ultracook`, while the current compatibility skill redirects it. The integration keeps the `/cook` redirect because it is the active implementation path.
- `skills/cheese/SKILL.md`: several sections repeat detailed reference rules. The integration keeps short router rules and reference-owned details to prevent future drift.

## Outward dependencies

- `this -> briesearch`: dispatches `/briesearch` for research and internal escalation.
- `this -> culture`: dispatches `/culture` for internal reasoning and read-only discussion.
- `this -> mold`: dispatches `/mold` and consumes its specification pointer.
- `this -> cook`: dispatches `/cook` and redirects retired `/ultracook` invocations.
- `this -> pasteurize`: dispatches `/pasteurize` for unexplained failures.
- `this -> press`: resumes the Press corrective Cook contract.
- `this -> age`: dispatches `/age` for review work.
- `this -> cure`: dispatches `/cure` for selected findings.
- `this -> plate`: dispatches `/plate` and forwards publication flags.
- `this -> affinage`: resumes clean, approved legacy pull request notes.
- `this -> wheypoint`: calls `/wheypoint resolve --ref` and `/wheypoint lint`.
- `this -> shared`: calls `resolve_slug` in `src/easy_cheese/shared/paths.py`.
- `this -> schemas`: consumes the phase registry and registered contract catalog.
- `build -> this`: `scripts/render_generated_regions.py` writes `schema-intertwine.md`.

## STE100 status

compliant

## Follow-ups

none
