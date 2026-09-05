## Summary

The combined build logic keeps one source for each command, closure, documentation, and bundle check.
The bundle build updates 13 archives.
`just check` passes.

## Commits

- `a5dd7b8` ingests the build slice from PR #592.
- `3e96ed7` ingests the build slice from PR #568.
- `c618b6b` ingests the build slice from PR #581.
- `6f895a7` ingests the build slice from PR #582.
- `94402c7` ingests the build slice from PR #586.
- `63f975d` ingests the build slice from PR #589.
- `a0339cf` rebuilds the integrated skill archives.

## Source PRs

- #568
- #581
- #582
- #586
- #589
- #592

## Disagreements

none

## Outward dependencies

- `this -> shared`: `scripts/render_generated_regions.py` imports `Command` and `command_map` from `easy_cheese.shared.bundle_commands`.
- `this -> schemas`: `scripts/render_generated_regions.py` imports contract models and compiled schema registries from `easy_cheese_schemas`.
- `this -> skills`: `scripts/check_bundles.py` checks skill sources, command targets, bundle references, and generated archives.
- `this -> skills`: `scripts/render_generated_regions.py` reads command manifests and emits `skills/*/references/commands.md`.
- `this -> skills`: `scripts/build_pyz.py` emits `skills/*/scripts/*.pyz`.
- `this -> docs`: `scripts/gen_docs.py` emits the website content tree and sidebar.
- `this -> docs`: `.github/workflows/docs.yml` builds and deploys the website.

## STE100 status

compliant

## Follow-ups

none
