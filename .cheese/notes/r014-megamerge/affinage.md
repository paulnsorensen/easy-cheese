# Affinage reconciliation

## Summary

- The affinage area now has one command manifest and one generated command inventory.
- The skill prose now states each workflow rule with short, active sentences.
- The rebuilt bundles include the integrated command boundary changes.

## Commits

- `91a220f` ingests the affinage slice from PR #592.
- `82afcd2` ingests the affinage slice from PR #581.
- `9beff53` removes the superseded local summary helper during shared reconciliation.
- The final reconciliation commit includes this note, the prose audit, and rebuilt bundles.

## Source PRs

- PR #581 adds manifest-based command documentation with required summaries.
- PR #592 adds enforceable skill boundaries.

## Disagreements

- `src/easy_cheese/skills/affinage/commands.py`: PR #581 added `_with_summary` around each command.
  The shared reconciliation added `derive_command` for the same purpose.
  This area keeps `derive_command` because it removes duplicate local code.

## Outward dependencies

- `this -> shared`: `easy_cheese.shared.bundle_commands` supplies `bundle_command`, `derive_command`, and `dispatch`.
  `derive_command` now supplies each required command summary.
- `this -> shared`: `easy_cheese.shared.fanout.age_route_cli.main` selects the `/age` route.
  Its contract does not change.
- `this -> shared`: `easy_cheese.shared.fanout.review_surface_cli.main` scores the review surface.
  Its contract does not change.
- `this -> age`: `/age`, its dimensions, its voice rules, and its report format supply review grading.
  These contracts do not change.
- `this -> cheese`: portability, handoff, and agent resolution references define shared control contracts.
  These contracts do not change.
- `this -> cure`: `.cheese/affinage/pr-<n>.md` and `handoff_context` send selected findings to `/cure`.
  The `source_skill: /affinage` value keeps publication in affinage.
- `this -> melt`: `/melt` resolves merge conflicts before `/cure`.
  Its contract does not change.
- `this -> plate`: `/plate` publishes fixes after approved replies post.
  Its contract does not change.
- `this -> hard-cheese`: `--hard` reaches `/hard-cheese` through terminal `/plate`.
  Its contract does not change.
- `this -> pasteurize`: `/pasteurize` can test an investigation claim.
  Its contract does not change.
- `this -> briesearch`: `/briesearch` can inspect evidence outside the diff.
  Its contract does not change.
- `build -> this`: `scripts/build_pyz.py` packages `src/easy_cheese/skills/affinage/commands.py`.
  The rebuilt `skills/affinage/scripts/affinage.pyz` contains the command manifest.
- `build -> this`: `scripts/render_generated_regions.py` creates `references/commands.md` from `COMMANDS`.
  The generated inventory includes each required summary.

## STE100 status

compliant

## Follow-ups

none
