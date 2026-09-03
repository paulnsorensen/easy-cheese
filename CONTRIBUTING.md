# Contribute to easy-cheese

Thank you for your interest. We welcome contributions of all sizes. A typo fix is as useful as a feature.
This document explains how to prepare and submit a change.

## File an issue

- Search [open issues](https://github.com/paulnsorensen/easy-cheese/issues) before you open a new issue.
- Use the bug report template or the feature request template.
- Do not open a public issue for a security vulnerability. Read [`SECURITY.md`](./SECURITY.md).

## Local setup

Install Python 3.12 or later. Install bats-core and ShellCheck for the Bash tests.

```sh
git clone https://github.com/paulnsorensen/easy-cheese.git
cd easy-cheese
brew install just uv bats-core shellcheck yamllint yamlfmt markdownlint-cli2
just check
```

`just check` uses `uv` to resolve test tools temporarily. It does not install Shiv or rebuild the committed skill archives.

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
Use an immutable tuple of `Command(name, "module:callable")` values.
When you add or change a command, make its target accept `list[str]`.
Write result text to stdout. Write diagnostics to stderr. Return an integer process status.
Do not modify `sys.argv`. Do not run the target through `runpy`. Do not add a decorator-based registry.

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
# Validate skill YAML and frontmatter.
python3 .github/scripts/test_validate_skills.py -v
python3 .github/scripts/validate_skills.py

# Run Python unit tests.
python3 -m pytest tests/python -q

# Run Bash tests. These tests require bats-core and ShellCheck.
shellcheck scripts/install.sh
bats tests/bash/test_install.bats
```

Run the full test suite before you open a pull request.

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