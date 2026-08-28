# Contributing to easy-cheese

Thanks for your interest. Contributions of all sizes are welcome — a
typo fix is just as useful as a feature. This document describes how
to get from "I want to help" to "my change is merged".

## Filing issues

- Search [open issues](https://github.com/paulnsorensen/easy-cheese/issues)
  before opening a new one.
- Use the bug-report or feature-request template.
- For security vulnerabilities, do **not** open a public issue — see
  [`SECURITY.md`](./SECURITY.md).

## Setting up locally

Requires Python 3.12+ and (for bash tests) bats-core + shellcheck.

```sh
git clone https://github.com/paulnsorensen/easy-cheese.git
cd easy-cheese
brew install just uv bats-core shellcheck yamllint yamlfmt markdownlint-cli2
just check
```

`just check` resolves test tools ephemerally through `uv`. It does not install
Shiv or rebuild the checked-in skill archives.

## Rebuild skill archives

Each Python-backed skill ships one same-named Shiv archive at
`skills/<skill>/scripts/<skill>.pyz`. You need the build dependencies only when
you rebuild these archives; users run them with Python alone.

If you change runtime source under `src/easy_cheese/`, a phase contract, build
configuration, a bundle lock, or a committed archive, install the pinned build
tools and rebuild every archive:

```sh
python3 -m pip install --requirement requirements-build.txt
just bundle
```

`just bundle` resolves each application from PEP 517 wheels in a private
wheelhouse. It compares the resolved closure with the corresponding hash-locked
file under `requirements/bundles/`.

Each Python skill declares its public subcommands in `commands.py` as an
immutable tuple of `Command(name, "module:callable")` values. When you add or
change a command, make its target accept `list[str]`, write result text to
stdout or diagnostics to stderr, and return an integer process status. Do not
mutate `sys.argv`, execute the target through `runpy`, or add a decorator-based
registry.

If you intend to change the resolved dependency closure, update the locks
explicitly:

```sh
python3 scripts/build_pyz.py --update-locks
```

Commit the changed lock files and `skills/*/scripts/*.pyz` archives with the
source change. CI rebuilds the archives and compares their canonical member
content with the committed artifacts.

## Documentation style

For project terminology and established cheese flavor, follow the repository's
project-specific guidance first. For other editorial decisions, follow the
[Google developer documentation style guide](https://developers.google.com/style/).
Write directly to the reader, prefer active voice, use sentence case for
headings, format code-related names in backticks, and use descriptive link text.
Edit root documents such as `README.md` and `CONTRIBUTING.md`; the documentation
build generates their copies under `src/content/docs/`.

## Running tests

```sh
# Skill YAML/frontmatter validation
python3 .github/scripts/test_validate_skills.py -v
python3 .github/scripts/validate_skills.py

# Python unit tests
python3 -m pytest tests/python -q

# Bash tests (requires bats + shellcheck)
shellcheck scripts/install.sh
bats tests/bash/test_install.bats
```

Please run the full test suite before opening a PR.

## Submitting a pull request

1. Fork the repo and create a topic branch from `main`.
2. Make your change. Keep commits focused; one concern per commit is
   easier to review than a kitchen-sink commit.
3. Use [Conventional Commits](https://www.conventionalcommits.org)
   for the PR title (e.g. `feat: add X`, `fix: handle Y`,
   `docs: explain Z`). Squash-merge will use the PR title as the
   commit subject.
4. Fill out the PR template — the "why" matters more than the "what".
5. Wait for CI to go green and address review feedback.

## Code of Conduct

Participation in this project is governed by the
[Contributor Covenant](./CODE_OF_CONDUCT.md). By contributing you
agree to abide by it.

## Licensing

By submitting a contribution you agree that it will be licensed under
the same terms as the project itself (see [`LICENSE`](./LICENSE)).
