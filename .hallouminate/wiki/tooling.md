# Tooling

The build, validation, and tool-dependency surface for easy-cheese. The
guiding rule: one local gate (`just check`), mirrored read-only in CI
(`just ci`).

## `just check` vs `just ci`

`just check` is the local pre-flight; `just ci` is the same gate without
autofixes (`justfile:77,80`). Run `just check` before any commit, push,
PR, or hand-off (`AGENTS.md:7`).

| | `just check` | `just ci` |
|---|---|---|
| markdown | `lint-md-fix` (autofix) | `lint-md` (check only) |
| yaml | `lint-yaml-fix` + `lint-yaml` | `lint-yaml` |
| python | `lint-py-fix` (`uvx ruff check --fix .`) | — |
| dead code | `lint-py-dead-code` (owner-qualified Vulture classifier) | `lint-py-dead-code` |
| shell | `lint-sh` (`shellcheck scripts/install.sh`) | `lint-sh` |
| tests | `test` | `test` |
| docs | `docs-build` (`pnpm run docs:build` → Astro/Starlight) | `docs-build` |

**Vulture is whitelist-free.** `scripts/check_dead_code.py` wraps
Vulture 2.16's scan and accepts findings only in narrow,
owner-qualified categories (schema-owned enum members/attrs fields,
exact stdlib callback overrides, autouse pytest fixtures); everything
else fails the gate. `lint-py-dead-code` runs in both `check` and `ci`,
so there is no local/CI skew. Twenty findings outside those categories
carry local `# noqa: V1xx` comments instead of a checked-in symbol
list. Vulture counts `getattr(x, "name")`/`hasattr(x, "name")` string
literals as reads, but a `getattr(module, variable)` read is invisible
to it; give such attributes one literal read (a stronger assertion
usually works) or a local `# noqa`.

Two gaps the remaining asymmetry has bitten:

- **`lint-yaml-fix` (in `check`, not `ci`) restyles `pnpm-lock.yaml`**
  into `? key : value` complex-key form. CI's `yamllint` accepts the
  committed pnpm-native form, so that churn is never required — leave it
  uncommitted.
- **CI pins `pytest==9.0.3`** (`validate.yml`) while dev environments
  track newer pytest (9.1+). Code that touches pytest internals — the
  cut assertion probe's console seam, for example — must feature-detect:
  pytest 9.1 moved `pytest.__main__`'s entry to the private
  `_pytest.config._console_main`; older releases call the public
  `pytest.console_main`. A dev-green/CI-red split on native-runner tests
  is usually this version skew.

The `test` recipe runs the skill + wiki validator self-tests and
validators (`test_validate_skills.py`, `test_validate_wiki.py`,
`validate_skills.py`, `validate_wiki.py`), the pytest suites
(`tests/python`, `tests/shared/python`, `tests/fanout/python`,
`tests/schemas/python`, `tests/hard-cheese/python`,
`tests/pasteurize/python`, `tests/wheypoint/python`), the JS suite
(`node --test tests/js`), the bats suites
(`tests/bash/test_install.bats`, the fan-out bats), and
`just test-skill-overlap` (`justfile:17-33`).

`test-skill-overlap` is the one leg of the gate that is not Python, JS,
or bash: it is `cargo test` against `tools/skill-overlap/`
(`justfile:36-37`), so a machine without a Rust toolchain cannot run
`just check` to completion even though everything else in the repo is
Python-and-markdown. It is deliberately model-free — the analyzer's
model artifacts are never fetched during the gate.

Note the markdownlint globs are `skills/**/*.md`, `.agents/**/*.md`, and
`*.md` (`justfile:52-58`) — files outside those globs (for example this
wiki under `.hallouminate/wiki/`) are not linted by the gate, so keep
their markdown clean by hand. `validate_wiki.py` does run over the wiki
in `just test`, but its checks are structural only — single leading H1,
kebab-case stem, index markers present, and index entries and files
resolving to each other in both directions. Frontmatter and lifecycle
checks are deliberately *not* there (a separate seam, issue #206), and
discovery is hardcoded to `.hallouminate/wiki/` rather than read from
`config.toml` corpus paths
([adr/hallouminate-wiring-stack-004](./adr/hallouminate-wiring-stack-004.md)).
So a wiki page can be committed with broken links, stale citations, or —
as PR #398 proved — literal merge-conflict markers, and still pass the
gate.

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

## Source-code routing vs optional MCPs

- **The shared contract names backend shape.** Workflow skills link
  `skills/cheese/references/code-intelligence-routing.md` and call the selected
  backend directly. The retired code-intelligence wrapper skills previously
  carried this policy.
- **Backend choice is conditional.** LSP wins for type-grounded
  definitions/references/renames/code actions; `sg` wins for structural
  metavariable patterns and codemods; tilth wins for broad source
  search/read/edit context in one fresh repo scan.
- **Optional MCPs are separate.** Context7, Tavily, hallouminate, and milknado
  help workflow skills, but they do not change the source-code routing rule.
- **Plain shell fallbacks are weaker evidence.** Use blind
  `grep`/`cat`/`sed`/`patch` only when no semantic backend exists, bound the
  operation, and report the precision loss.
- **Workflow skills stay portable.** There is no repo-wide MCP requirement.

## `.pyz` bundles

Skills that consume `shared/scripts/` ship a pre-built `.pyz` so the
shared helpers are self-contained at install time, invoked as
`python3 skills/<skill>/scripts/<skill>.pyz <subcommand>`
(`skills/mold/SKILL.md:23`). The roster is the `SKILLS` dict in
`scripts/build_pyz.py`: affinage, age, briesearch, cook, cut,
easy-cheese-setup, hard-cheese, melt, mold, pasteurize, press,
ultracook, and wheypoint each ship their own bundle, and a shared
`common.pyz` is additionally fanned into age, cure, and ultracook
(`COMMON_CONSUMERS`) so a consumer-only skill is still self-contained
after install.

**The bundles are committed artifacts, and CI only checks them — it does
not regenerate them.** `build-pyz.yml` runs with `permissions: contents:
read`, builds into a scratch tree, and then runs
`scripts/check_bundles.py`; there is no commit step. Change anything
under `src/`, `shared/scripts/`, or the vendored deps without running
`just bundle` and the PR goes red rather than being silently fixed up.
The `bundle` recipe's own comment still says "CI rebuilds on every push
to main" (`justfile:39`) — that comment is stale; the workflow is the
authority.

`check_bundles.py` compares member CRCs, not raw bytes, because
`ZIP_DEFLATED` output differs between zlib and zlib-ng builds — a
byte-level comparison would fail for every contributor whose toolchain
differs from whoever last committed the bundles.

`just bundle` depends on `just vendor`: `vendor/` is generated from
hash-pinned `requirements-vendor.txt` rather than committed, so a bundle
rebuild is deterministic but **not** offline.

## CI workflows

Under `.github/workflows/`:

| Workflow | Trigger | Does |
|---|---|---|
| `validate.yml` | push main, all PRs | frontmatter validation, pytest, install.sh bats + smoke, lint |
| `build-pyz.yml` | PRs + push main (`src/**`, `shared/scripts/**`, build script, vendored deps, the bundles themselves) | rebuild into scratch and **verify** committed `.pyz` bundles are current — never commits |
| `release.yml` | tag `v[0-9]*` | stage slim tree, force-push `release` branch, GitHub release |
| `publish-pypi.yml` | push main touching `pyproject.toml`, dispatch | publish `easy-cheese-schemas` to PyPI |
| `docs.yml` | push/PR on docs paths, dispatch | `pnpm run docs:build` (Astro/Starlight), deploy Pages on main |
| `docs-retry.yml` | `docs` workflow_run failure | auto re-run failed `docs` jobs on main, up to 3 attempts |
| `skill-overlap.yml` | PRs on `skills/**/*.md` + tools, weekly cron, dispatch | semantic skill-overlap ratchet (`calibrate` / `report` / `check`) |
| `codeql.yml` | PRs, push main, weekly | CodeQL on python + actions |
| `dependency-review.yml` | PRs to main | block vulnerable / disallowed-license deps |
| `scorecard.yml` | push main, weekly | OpenSSF Scorecard → SARIF |
| `copilot-review.yml` | PR opened/reopened/ready | add Copilot as reviewer |

### Prerequisites

`just`, `uv` (for `uvx ruff`), plus `yamllint`, `yamlfmt`,
`markdownlint-cli2`, `shellcheck`, and `bats` — see `README.md` for
install hints (`AGENTS.md:18-21`).
