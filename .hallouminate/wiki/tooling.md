# Tooling

The build, validation, and tool-dependency surface for easy-cheese. The
guiding rule: one local gate (`just check`), mirrored read-only in CI
(`just ci`).

## `just check` vs `just ci`

`just check` is the local pre-flight; `just ci` is the same gate without
autofixes (`justfile:51-54`). Run `just check` before any commit, push,
PR, or hand-off (`AGENTS.md:7`).

| | `just check` | `just ci` |
|---|---|---|
| markdown | `lint-md-fix` (autofix) | `lint-md` (check only) |
| yaml | `lint-yaml-fix` + `lint-yaml` | `lint-yaml` |
| python | `lint-py-fix` (`uvx ruff --fix`) | — |
| shell | `lint-sh` (`shellcheck scripts/install.sh`) | `lint-sh` |
| tests | `test` | `test` |
| docs | `docs-build` (`mkdocs build --strict`) | `docs-build` |

The `test` recipe runs the validator self-test, `validate_skills.py`,
the pytest suites (`tests/python`, `tests/shared/python`,
`tests/cheese-factory/python`), and the bats suites
(`tests/bash/test_install.bats`, the cheese-factory bats)
(`justfile:8-16`).

Note the markdownlint globs are `skills/**/*.md` and `*.md`
(`justfile:31-35`) — files outside those globs (for example this wiki
under `.hallouminate/wiki/`) are not linted by the gate, so keep their
markdown clean by hand.

## Validators

`.github/scripts/validate_skills.py` enforces the skill contract on every
`skills/<name>/SKILL.md` (`.github/scripts/validate_skills.py`):

- Path must be exactly `skills/<name>/SKILL.md` — nested sub-skills
  rejected (line 43).
- YAML frontmatter present, parseable, and a mapping (lines 53-62).
- `name` required, kebab-case
  (`^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$`), and equal to the parent
  directory name (lines 69-82).
- `description` required, non-empty, ≤ 1024 chars — the Codex limit
  (lines 84-92).
- No keys outside the allow-list (`name`, `description`, `license`,
  `compatibility`, `metadata`, `allowed-tools`, `version`,
  `argument-hint`, `disable-model-invocation`, `user-invocable`, `model`,
  `context`, `agent`, `hooks`) (lines 18-33, 94-96).

`test_validate_skills.py` is the unittest suite covering those rules.

## tilth / cheez-* hard-fail vs optional MCP

Tool dependency is asymmetric by design:

- **`cheez-*` skills require tilth MCP and hard-fail without it.** They
  refuse to fall back to `grep`/`cat`/`Edit`
  (`skills/cheez-search/SKILL.md:3-5`, `AGENTS.md:73`).
- **Every other skill stays portable** and degrades to host-native tools.
  Workflow skills only *suggest* tilth, Context7, Tavily, and
  code-review-graph; there is no repo-wide MCP requirement
  (`README.md:87,161`).

The trade is intentional: the tool skills buy AST-grounded precision and
announce the cost by refusing to run without it; the workflow skills stay
universal.

## `.pyz` bundles

Skills that consume `shared/scripts/` ship a pre-built `.pyz` so the
shared helpers are self-contained at install time, invoked as
`python3 ${CLAUDE_SKILL_DIR}/scripts/<skill>.pyz <subcommand>`
(`skills/mold/SKILL.md:22`). Bundles exist for affinage, briesearch,
cheese-factory, cook, melt, and mold. `just bundle` rebuilds them locally
(`scripts/build_pyz.py`); `build-pyz.yml` rebuilds and commits them on
every relevant push to `main` (`justfile:18-19`).

## CI workflows

Under `.github/workflows/`:

| Workflow | Trigger | Does |
|---|---|---|
| `validate.yml` | push main, all PRs | frontmatter validation, pytest, install.sh bats + smoke, lint |
| `build-pyz.yml` | push main (`src/**`, `shared/scripts/**`, build script) | rebuild + commit `.pyz` bundles |
| `release.yml` | tag `v[0-9]*` | stage slim tree, force-push `release` branch, GitHub release |
| `docs.yml` | push/PR on docs paths, dispatch | `mkdocs build --strict`, deploy Pages on main |
| `codeql.yml` | PRs, push main, weekly | CodeQL on python + actions |
| `dependency-review.yml` | PRs to main | block vulnerable / disallowed-license deps |
| `scorecard.yml` | push main, weekly | OpenSSF Scorecard → SARIF |
| `copilot-review.yml` | PR opened/reopened/ready | add Copilot as reviewer |

### Prerequisites

`just`, `uv` (for `uvx ruff`), plus `yamllint`, `yamlfmt`,
`markdownlint-cli2`, `shellcheck`, and `bats` — see `README.md` for
install hints (`AGENTS.md:18-21`).
