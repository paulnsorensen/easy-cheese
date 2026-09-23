# Bundle command dispatch

Every `.pyz` bundle routes its first argument through `bundle_commands.dispatch`. The dispatcher forgives a caller mistake only when the intent is certain. It never runs a guess. The build of the bundles is a separate topic: see [[architecture/pyz-bundling-pipeline]].

## Why the dispatcher forgives

Bundle command dispatch changed after session analytics over 2,286 bundle calls. About 8% of calls ended in a bare `usage:` line, and 29% of sessions hit one. The misuse was not misspelling. It was top-level `--help` (84% of the dead ends), a nested leaf called at the top level, a command of another bundle, a flag before the command, and two arguments inside one quoted token. Edit-distance matching fits almost none of these cases, so the guidance is an exact-name lookup first.

## Top-level help and unknown-command guidance

Bundle command dispatch prints one help block for `--help`, `-h`, `help`, and no arguments (`src/easy_cheese/shared/bundle_commands.py:258`). The block has the usage line, one `name  summary` line per command, and pointers to `<command> --help` and `references/commands.md`. No arguments returns 2; the other forms return 0. A real command named `help` wins over the alias. Top-level `--version` reads installed `easy-cheese-shared` metadata and returns 0 without running a command (`src/easy_cheese/shared/bundle_commands.py:267`).

For an unknown name, `_unknown_command_message` (`src/easy_cheese/shared/bundle_commands.py:179`) adds guidance below the usage line, on stderr, with exit 2:

- A nested leaf of this bundle: `'compute' is a subcommand of 'severity'. Run: <pyz> severity compute ...`
- A command of another bundle: `'severity' is a command of age.pyz.`
- A leaf of another bundle: `'create' is 'worktree create' in cook.pyz.`
- Otherwise a `difflib` close match: `Did you mean: show?`

One helper, `_lookup` (`src/easy_cheese/shared/bundle_commands.py:163`), accepts `_` as an alias of `-` for the command and for every guidance table. `stack_tools` gets the same guidance as `stack-tools`.

## Leading-flag hoist rule

Bundle command dispatch reads `argv[0]` as the command, so a flag before the command is a caller mistake. `_hoisted_leading_flags` (`src/easy_cheese/shared/bundle_commands.py:219`) moves only `--json` and `--full` after the command and prints `note: moved --json after 'severity'`. Each Cyclopts command declares the supported flags; dispatch moves only these two valueless flag names.

Any other leading flag exits 2 with `Put the command first` and names the flag. The reason is a security one: the value of a flag can equal a command name. An earlier rule hoisted every dash token, and `age.pyz --slug handoff review-lock` then ran `handoff` with shifted arguments. A help flag among the leading flags prints the top-level help.

`dispatch` also rewrites `--flag_name` to `--flag-name` before the handler runs, and leaves every token after a bare `--` unchanged (`src/easy_cheese/shared/bundle_commands.py:239`). A guard test fails when a parser declares a long option with an underscore.

## Quote repair rule

`cli.run` accepts a Cyclopts `App`. It probes parsing before invocation, then invokes the selected handler once (`src/easy_cheese/shared/cli.py:52`). Parse errors return 2. The shipped parser path has no argparse compatibility layer.

Quote repair handles a token such as `--files '2 --modules 2'`. It uses Cyclopts argument metadata to select only declared scalar, non-free-text option values. It then uses `shlex` if the token contains whitespace and one piece resembles an option (`src/easy_cheese/shared/argv_repair.py:65-94`). It keeps the original argv when it parses, when help appears, or when no unique split candidate parses. It stops before a bare `--` and prints a note for one accepted repair (`src/easy_cheese/shared/argv_repair.py:97-125`). Probe parsing never runs handlers.

**One argv for a gate.** The age review-lock gate repairs with the writer's Cyclopts app before it peeks at `--slug`, `--phase`, and `--root`. It passes that same canonical argv to the writer (`src/easy_cheese/skills/age/review_lock.py:614`). The gate denies an age report over inline fixes before the writer runs.

`read_mapping_arg_or_stdin` rejects an `argv[0]` that starts with `-` with the handler's usage error (`src/easy_cheese/shared/manifest_io.py:35`). A hoisted `--json` therefore never becomes a manifest path.

## Leaves and the cross-bundle command index

Bundle command dispatch needs two static tables for its guidance, because a bundle cannot import another skill.

- **Leaves.** Each shared parser module exports a `LEAVES` tuple beside its Cyclopts commands (for example `src/easy_cheese/shared/severity.py:132`). Each skill `commands.py` passes it as `derive_command(..., leaves=<module>.LEAVES)`. A drift test compares declared leaves with each command's real Cyclopts `--help` output (`tests/python/test_bundle_commands.py:380`). A new nested command without declared leaves fails the test.
- **Index.** `scripts/_bundle_command_index_compiler.py` projects every skill's `COMMANDS` into `src/easy_cheese/shared/bundle_command_index.py` (`COMMAND_BUNDLES` and `LEAF_OWNERS`). `just update-generated` writes the file, and the build checks that it is current (`scripts/build_pyz.py:159`). The dispatcher reads both tables directly, and it survives a missing index module.

`references/commands.md` lists the leaves of each command in a last `Subcommands` column. The column is last because `tests/python/test_easy_cheese_setup_contract.py` pins the `| name | summary |` prefix of each row.

_Source: PR #702, its /age review, session analytics of `.pyz` calls, and the Cyclopts migration · Updated: 2026-09-23_
