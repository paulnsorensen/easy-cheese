## Summary

The area now has one command manifest for the `global`, `local`, and `doctor` commands.
The command summaries use the Hallouminate product name consistently.
The skill instructions now use ASD-STE100 prose.
The rebuilt bundles contain the integrated source state.

## Commits

- `c4d1174d6d22a10bcbf03c7b5086291962d2d664` reconciles the area and rebuilds the bundles.
- The next commit adds this notes file.

## Source PRs

- #581

## Disagreements

none

## Outward dependencies

- `this -> shared`: `commands.py` imports `Command` and `dispatch` from `easy_cheese.shared.bundle_commands`. The manifest now supplies `Command.summary` for generated command documentation.
- `this -> shared`: The command targets call `global_main`, `local_main`, and `doctor_main` in `easy_cheese.shared.hallouminate_setup`. This area does not change those contracts.
- `build -> this`: `scripts/build_pyz.py` packages the command manifest as `skills/easy-cheese-setup/scripts/easy-cheese-setup.pyz`. This contract does not change.
- `build -> this`: `scripts/render_generated_regions.py` reads `COMMANDS` and writes `references/commands.md`. The summaries now use the Hallouminate product name.
- `build -> this`: `scripts/install.sh` calls `global --apply` through the bundle. This command contract does not change.

## STE100 status

compliant

## Follow-ups

none
