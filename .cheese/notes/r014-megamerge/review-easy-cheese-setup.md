# Easy-cheese-setup Area Review

## Verdict

reject

One blocker can delete unrelated Hallouminate configuration.
One high finding breaks the tenant repair promise.
Three medium findings affect reports, help, and path guidance.

## Blocker

- **[correctness] The skill names an incomplete closing marker.** `skills/easy-cheese-setup/SKILL.md:39` tells the agent to use `# <<<`. The runtime requires `# <<< easy-cheese:cheese-durable` at `src/easy_cheese/shared/hallouminate_setup.py:31-32`. An unmatched start marker spans through end-of-file at `hallouminate_setup.py:76-92`. A probe used the documented marker before a repository section. `global --apply` removed that section during drift repair. **Fix:** Use the exact `END` marker in the skill prose.

## High

- **[spec] The skill routes tenant repair to a registration-only target.** `skills/easy-cheese-setup/SKILL.md:7-9` and `src/easy_cheese/skills/easy_cheese_setup/commands.py:15-19` promise repair. `apply_local` treats any existing configuration file as complete at `src/easy_cheese/shared/hallouminate_setup.py:277-295`. A probe left an empty tenant file unchanged and returned `noop`. **Fix:** Validate the repository name and path. Run `hallouminate init-repo <name> --path <main-root> --force` when values differ. Replace the empty-file test with repair expectations.

## Medium

- **[correctness] The global dry run hides directory creation.** `skills/easy-cheese-setup/SKILL.md:34,56` requires a report for every proposed change. `apply_global` derives its action from configuration state at `src/easy_cheese/shared/hallouminate_setup.py:172-184`. It always creates the corpus directory during apply at `hallouminate_setup.py:186-195`. A probe reported `noop` before `--apply` created the missing directory. `SKILL.md:58` also says the installer changes only the marked block. **Fix:** Report directory creation as a separate global change. Correct the installer statement.
- **[spec] Help advertises an invalid migration option.** `skills/easy-cheese-setup/SKILL.md:41-47` limits migration to `global`. `skills/easy-cheese-setup/references/commands.md:3` says help lists each command's arguments. `_leg_main` adds `--migrate-legacy` for every command, then rejects it for two commands at `src/easy_cheese/shared/hallouminate_setup.py:314-323`. Bundle probes showed the invalid option in `local --help` and `doctor --help`. **Fix:** Add the option only for `global`. Add exact help tests for all three commands.
- **[spec] The skill names one configuration path as universal.** `skills/easy-cheese-setup/SKILL.md:39` names `~/.config/hallouminate/config.toml`. `config_path` honors `HALLOUMINATE_CONFIG` and `XDG_CONFIG_HOME` at `src/easy_cheese/shared/hallouminate_setup.py:47-57`. This instruction can send manual inspection to the wrong file. **Fix:** Refer to `config_path()` as the source. State the default path separately.

## Low

- **[deslop] The skill uses two terms for each of two meanings.** `skills/easy-cheese-setup/SKILL.md:22,49` uses `subcommand` and `repo`. The area otherwise uses `command` and `repository`. **Fix:** Use `command` and `repository` throughout the prose.

## Simplifications

- Replace the direct `Command` constructors at `src/easy_cheese/skills/easy_cheese_setup/commands.py:7-25` with `derive_command`. Decorate the three shared entry points.
- Make `hallouminate_setup.main` select the command and call `_leg_main`. Remove the duplicate parser at `src/easy_cheese/shared/hallouminate_setup.py:338-357`.
- Keep one tenant-state validator. Use it for dry runs, repair decisions, and apply operations.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| easy-cheese-setup -> shared: `Command` and `dispatch` | ok | LSP resolved both imports to `src/easy_cheese/shared/bundle_commands.py:20-58,138-154`. The source manifest validation returned `ok`. |
| skill prose -> shared: `BEGIN` and `END` markers | broken | `skills/easy-cheese-setup/SKILL.md:39` omits the identifier from `END`. The deletion probe confirmed the risk. |
| `global` -> shared: `global_main` | broken | The target exists at `src/easy_cheese/shared/hallouminate_setup.py:326-327`. Its dry run does not report missing-directory creation. |
| `local` -> shared: `local_main` | broken | The target exists at `hallouminate_setup.py:330-331`. It cannot satisfy the repair summary at `commands.py:15-19`. |
| `doctor` -> shared: `doctor_main` | broken | The target exists at `hallouminate_setup.py:334-335`. Its help lists an option that it rejects. |
| build -> easy-cheese-setup: bundle packaging | ok | `scripts/build_pyz.py:334-350,461-527` derives the package and console entry point. The checked bundle dispatched all three commands. |
| build -> easy-cheese-setup: command reference | ok | `scripts/render_generated_regions.py:265-300` reads `COMMANDS`. `skills/easy-cheese-setup/references/commands.md:5-9` matches all names and summaries. |
| installer -> easy-cheese-setup: `global --apply` | ok | `scripts/install.sh:359-381` invokes the bundle. Four focused installer tests passed. |

Thirty focused setup tests passed.
Four focused installer tests passed.
The checked bundle dispatched all three commands.
Four bundle fixture tests skipped.
Five generic command tests failed before area assertions because the environment lacks `attrs`.

## STE100 status

- `skills/easy-cheese-setup/SKILL.md:22,49` violates the one-term rule. Use `command` and `repository`.
- `skills/easy-cheese-setup/references/commands.md` is compliant.

## Follow-ups

- Correct the closing marker before merge.
- Implement tenant repair through the shared setup target.
- Make the shared dry run report directory creation.
- Remove the invalid migration option from `local` and `doctor` help.
- Correct the configuration path guidance.
- Apply the two STE100 term changes.
- Restore the generic command tests after the build environment provides `attrs`.
- Run the four skipped bundle tests in the build environment.
