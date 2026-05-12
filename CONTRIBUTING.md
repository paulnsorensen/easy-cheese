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
pip install pyyaml==6.0.2 pytest==9.0.3   # validation + Python tests
brew install bats-core shellcheck           # macOS — bash tests
```

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
