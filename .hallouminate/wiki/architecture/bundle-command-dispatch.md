# Bundle command dispatch

Every `.pyz` bundle routes its first argument through `bundle_commands.dispatch`. The dispatcher forgives a caller mistake only when the intent is certain. It never runs a guess. The build of the bundles is a separate topic: see [[architecture/pyz-bundling-pipeline]].

## Why the dispatcher forgives

Bundle command dispatch changed after session analytics over 2,286 bundle calls. About 8% of calls ended in a bare `usage:` line, and 29% of sessions hit one. The misuse was not misspelling. It was top-level `--help` (84% of the dead ends), a nested leaf called at the top level, a command of another bundle, a flag before the command, and two arguments inside one quoted token. Edit-distance matching fits almost none of these cases, so the guidance is an exact-name lookup first.

## Top-level help and unknown-command guidance

Bundle command dispatch prints one help block for `--help`, `-h`, `help`, and no arguments (`src/easy_cheese/shared/bundle_commands.py:152`). The block has the usage line, one `name  summary` line per command, and pointers to `<command> --help` and `references/commands.md`. No arguments returns 2; the other forms return 0. A real command named `help` wins over the alias.

For an unknown name, `_unknown_command_message` (`src/easy_cheese/shared/bundle_commands.py:179`) adds guidance below the usage line, on stderr, with exit 2:

- A nested leaf of this bundle: `'compute' is a subcommand of 'severity'. Run: <pyz> severity compute ...`
- A command of another bundle: `'severity' is a command of age.pyz.`
- A leaf of another bundle: `'create' is 'worktree create' in cook.pyz.`
- Otherwise a `difflib` close match: `Did you mean: show?`

One helper, `_lookup` (`src/easy_cheese/shared/bundle_commands.py:163`), accepts `_` as an alias of `-` for the command and for every guidance table. `stack_tools` gets the same guidance as `stack-tools`.

## Leading-flag hoist rule

Bundle command dispatch reads `argv[0]` as the command, so a flag before the command is a caller mistake. `_hoisted_leading_flags` (`src/easy_cheese/shared/bundle_commands.py:219`) moves only `--json` and `--full` after the command and prints `note: moved --json after 'severity'`. `fromargs` owns these two global flags and strips them anywhere before `--`: `--json` is a no-op because output is always JSON, and `--full` turns off a command's `limit=` truncation.

Any other leading flag exits 2 with `Put the command first` and names the flag. The reason is a security one: the value of a flag can equal a command name. An earlier rule hoisted every dash token, and `age.pyz --slug handoff review-lock` then ran `handoff` with shifted arguments. A help flag among the leading flags prints the top-level help.

`dispatch` also rewrites `--flag_name` to `--flag-name` before the handler runs, and leaves every token after a bare `--` unchanged (`src/easy_cheese/shared/bundle_commands.py:239`). A guard test fails when a parser declares a long option with an underscore.

## Quote repair rule

Quote repair fixes one bundle call shape: `--files '2 --modules 2'` arrives as one token. Every bundle command that builds a `fromargs.App` gets the repair from `fromargs` itself (`skillz-that-grillz` `lib/fromargs`, the PyPI release pinned in `requirements/runtime.txt`). `fromargs` splits a token only when the app rejects the original argv, the token is the value of an option that cannot hold free text (not a flag, not an unconstrained `str` or path), and exactly one split candidate parses. It never splits a positional or free-text value, stops at `--`, and never splits a token that would free a help or version flag. The `note: split quoted argument ...` line names the pieces. `tests/shared/python/test_forgiving_cli_press.py` locks this behavior through a real `fromargs.App`.

**Output contract.** A `fromargs` handler returns data. `fromargs` prints it as one indented JSON document on stdout, and reports every refusal as one stderr line `{"error": <message>, "exit_code": <n>}`. Only a raised `fromargs.CliError` sets a nonzero exit, so an outcome that is not an error (for example a stale `freshness-check` state or `debug-tag-sweep` tags) is a field in the JSON, not an exit code.

**One parse for a gate.** The age review-lock gate `gated_write_handoff_artifact` does not peek at argv. It builds the writer app with `write_handoff_artifact.build_app(before_write=...)`; the writer's own parse hands `(slug, phase, root)` to the hook before any write (`src/easy_cheese/skills/age/review_lock.py`). The gate and the writer therefore always read the same `--slug`.

`read_mapping_arg_or_stdin` rejects an `argv[0]` that starts with `-` with the handler's usage error (`src/easy_cheese/shared/manifest_io.py:35`). A hoisted `--json` therefore never becomes a manifest path.

## Leaves and the cross-bundle command index

Bundle command dispatch needs two static tables for its guidance, because a bundle cannot import another skill.

- **Leaves.** Each shared parser module exports a `LEAVES` tuple beside its `add_subparsers` call (for example `src/easy_cheese/shared/severity.py:160`). Each skill `commands.py` passes it as `derive_command(..., leaves=<module>.LEAVES)`. A drift test compares every command of every skill with the subcommands in its real `--help` output (the `Commands:` section of `fromargs` plain help, or an argparse `{a,b} ...` group), with no allowlist (`tests/python/test_bundle_commands.py:389`). A new command with subparsers and no leaves fails the test.
- **Index.** `scripts/_bundle_command_index_compiler.py` projects every skill's `COMMANDS` into `src/easy_cheese/shared/bundle_command_index.py` (`COMMAND_BUNDLES` and `LEAF_OWNERS`). `just update-generated` writes the file, and the build checks that it is current (`scripts/build_pyz.py:159`). The dispatcher reads both tables directly, and it survives a missing index module.

`references/commands.md` lists the leaves of each command in a last `Subcommands` column. The column is last because `tests/python/test_easy_cheese_setup_contract.py` pins the `| name | summary |` prefix of each row.

_Source: PR #702 (forgiving bundle CLI), its /age review, and session analytics of `.pyz` calls · Updated: 2026-09-19_
