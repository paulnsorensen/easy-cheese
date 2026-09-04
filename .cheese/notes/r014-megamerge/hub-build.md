# Build Consumer Hub Review

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `wheypoint -> build` | untested | `src/easy_cheese/skills/wheypoint/commands.py:15-58` defines five commands with `@bundle_command` and `derive_command`. `scripts/build_pyz.py:40-44,334-350,507-538` finds the skill, packages its command module, and writes `wheypoint.pyz`. `scripts/render_generated_regions.py:269-300,308-333` imports `COMMANDS`, applies `command_map`, and writes `commands.md`. The checked file matches at `skills/wheypoint/references/commands.md:5-11`. Fifteen focused manifest tests passed. Two archive tests passed. A smoke test showed all five archive commands. However, the archive checker found no Wheypoint commands. Thus, no automated test checks each built command target. |

## Findings

### Blocker

none

### High

- `scripts/check_bundles.py:461-499,622-633` reads only literal `Command(...)` calls from archive trees. Wheypoint declares each command with `@bundle_command` and `derive_command` at `src/easy_cheese/skills/wheypoint/commands.py:15-58`. The probe returned `()`. Therefore, `_check_command_dispatch` never imports Wheypoint handlers from the built archive. **Fix:** Read `@bundle_command` names from the archive trees. Add a test that breaks one built Wheypoint target and requires the checker to fail.

### Medium

none

### Low

none

## STE100 status

compliant


## Follow-ups

- Make `scripts/check_bundles.py` discover `@bundle_command` entries. Add a test that fails when a built Wheypoint target is missing.
