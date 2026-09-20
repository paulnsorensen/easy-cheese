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

Bundle command dispatch reads `argv[0]` as the command, so a flag before the command is a caller mistake. `_hoisted_leading_flags` (`src/easy_cheese/shared/bundle_commands.py:219`) moves only `--json` and `--full` after the command and prints `note: moved --json after 'severity'`. `cli.run` injects these two flags into every parser, and they take no value.

Any other leading flag exits 2 with `Put the command first` and names the flag. The reason is a security one: the value of a flag can equal a command name. An earlier rule hoisted every dash token, and `age.pyz --slug handoff review-lock` then ran `handoff` with shifted arguments. A help flag among the leading flags prints the top-level help.

`dispatch` also rewrites `--flag_name` to `--flag-name` before the handler runs, and leaves every token after a bare `--` unchanged (`src/easy_cheese/shared/bundle_commands.py:239`). A guard test fails when a parser declares a long option with an underscore.

## Quote repair rule

Quote repair fixes one bundle call shape: `--files '2 --modules 2'` arrives as one token. `repair_split_quotes` (`src/easy_cheese/shared/argv_repair.py:84`) splits a token only when all of these hold:

- The token is the value of an option that cannot hold free text: the option has `choices`, or a `type` other than `str` (`src/easy_cheese/shared/argv_repair.py:38`). The previous token names the option, or the token uses the `--opt=` form.
- One piece is a declared option string.
- The original argv fails to parse, and the split argv parses.

The repair never splits a positional token or the value of a plain string option. An earlier rule split free text, and it could write a shortened `orientation` into a durable handoff. The repair stops at a bare `--`. It returns the original argv when a split frees `-h` or `--help`, because the probe parse would print a help page to stdout and corrupt a `--json` consumer. The note prints the pieces.

**Boundary.** `cli.run` and the age review-lock gate `gated_write_handoff_artifact` both call the public `cli.repair_argv` (`src/easy_cheese/shared/cli.py:70`). A handler that builds its own parser gets flag standardization from `dispatch`, but no quote repair.

**One argv for a gate.** A gate that peeks at argv before a `cli.run` handler must repair first. The age review-lock gate calls `cli.repair_argv(write_handoff_artifact.setup_parser, argv)` and passes that one list to the peek and to the writer (`src/easy_cheese/skills/age/review_lock.py:382`). Otherwise the gate and the writer can read different `--slug` values.

`read_mapping_arg_or_stdin` rejects an `argv[0]` that starts with `-` with the handler's usage error (`src/easy_cheese/shared/manifest_io.py:35`). A hoisted `--json` therefore never becomes a manifest path.

## Leaves and the cross-bundle command index

Bundle command dispatch needs two static tables for its guidance, because a bundle cannot import another skill.

- **Leaves.** Each shared parser module exports a `LEAVES` tuple beside its `add_subparsers` call (for example `src/easy_cheese/shared/severity.py:160`). Each skill `commands.py` passes it as `derive_command(..., leaves=<module>.LEAVES)`. A drift test compares every command of every skill with the `{a,b} ...` subparser group in its real `--help` output, with no allowlist (`tests/python/test_bundle_commands.py:389`). A new command with subparsers and no leaves fails the test.
- **Index.** `scripts/_bundle_command_index_compiler.py` projects every skill's `COMMANDS` into `src/easy_cheese/shared/bundle_command_index.py` (`COMMAND_BUNDLES` and `LEAF_OWNERS`). `just update-generated` writes the file, and the build checks that it is current (`scripts/build_pyz.py:159`). The dispatcher reads both tables directly, and it survives a missing index module.

`references/commands.md` lists the leaves of each command in a last `Subcommands` column. The column is last because `tests/python/test_easy_cheese_setup_contract.py` pins the `| name | summary |` prefix of each row.

_Source: PR #702 (forgiving bundle CLI), its /age review, and session analytics of `.pyz` calls · Updated: 2026-09-19_
