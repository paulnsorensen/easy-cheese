# Contribute to easy-cheese

Thank you for your interest. We welcome contributions of all sizes. A typo fix is as useful as a feature.
This document explains how to prepare and submit a change.

## File an issue

- Search [open issues](https://github.com/paulnsorensen/easy-cheese/issues) before you open a new issue.
- Use the bug report template or the feature request template.
- Do not open a public issue for a security vulnerability. Read [`SECURITY.md`](./SECURITY.md).

## Local setup

Install these prerequisites before you run the checks:

- Python 3.12 or later, for the Python suites and the documentation generator.
- `just` and `uv`, which resolve every Python tool for each recipe.
- bats-core and ShellCheck, for the Bash suites.
- yamllint, yamlfmt, and markdownlint-cli2, for the format checks.
- Node.js 22 or later with Corepack, for the JavaScript suite and the documentation build.
- Rust and Cargo, for the skill-overlap analyzer tests.

```sh
git clone https://github.com/paulnsorensen/easy-cheese.git
cd easy-cheese
brew install just uv bats-core shellcheck yamllint yamlfmt markdownlint-cli2 node rust
corepack enable
just check
```

`just check` uses `uv` to resolve the Python tools temporarily. It does not install Shiv. It does not rebuild the committed skill archives.

## Rebuild skill archives

Each Python skill includes one Shiv archive at `skills/<skill>/scripts/<skill>.pyz`.
Install the build dependencies only when you rebuild these archives. Users can run the archives with Python alone.

Rebuild every archive after you change runtime source under `src/easy_cheese/`, a phase contract, build configuration, or a committed archive.

```sh
python3 -m pip install --requirement requirements-build.txt
just bundle
```

`just bundle` resolves each application from PEP 517 wheels in a private wheelhouse.
It writes the complete external and internal hash-locked closure to a temporary requirements file beside that wheelhouse.
Then it invokes Shiv. The external runtime pins in `requirements/runtime.txt` are the only committed hash lock.

Each Python skill declares its public subcommands in `commands.py`.
Declare each handler with the `@bundle_command("<name>")` decorator at its definition site.
The decorator records the command name on the function. It does not create a mutable registry.
Compile each decorated handler into a command with `derive_command(handler, "<summary>")`.
Collect the results in an immutable `COMMANDS` tuple.
`validate_command_surface` rejects a declared name that `COMMANDS` omits.
It also rejects a `COMMANDS` entry that no decorator declares.
Make each handler accept `list[str]`.
Write result text to stdout. Write diagnostics to stderr. Return an integer process status.
Do not modify `sys.argv`. Do not run the target through `runpy`.
See `src/easy_cheese/skills/affinage/commands.py` for a complete manifest.

Commit the regenerated `skills/*/scripts/*.pyz` archives with the source change.
CI rebuilds the archives and compares their canonical member content with the committed artifacts.

## Documentation style

Follow the repository guidance for project terms and the established cheese flavor.
For other editorial decisions, follow the [Google developer documentation style guide](https://developers.google.com/style/).
Write directly to the reader. Use active voice and sentence case for headings.
Format code names with backticks. Use descriptive link text.
Edit root documents such as `README.md` and `CONTRIBUTING.md`. The documentation build generates copies under `website/content/docs/`.

## Run tests

```sh
# Run every suite: skill validators, Python, JavaScript, Bash, and Rust.
just test

# Run the full gate: format, lint, types, tests, documentation, and archives.
just check
```

Run `just check` before you open a pull request.

## Submit a pull request

1. Fork the repository and create a topic branch from `main`.
2. Make your change. Keep each commit focused on one concern. This structure helps reviewers.
3. Use [Conventional Commits](https://www.conventionalcommits.org) for the pull request title.
   Examples include `feat: add X`, `fix: handle Y`, and `docs: explain Z`.
   The squash merge uses the pull request title as the commit subject.
4. Complete the pull request template. Explain why the change is necessary.
5. Wait for CI to pass. Address the review comments.

## Code of Conduct

The [Contributor Covenant](./CODE_OF_CONDUCT.md) governs participation in this project.
You agree to follow it when you contribute.

## License

Your contribution uses the same license terms as the project. Read [`LICENSE`](./LICENSE).
