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
| shell | `lint-sh` (`shellcheck scripts/install.sh`) | `lint-sh` |
| tests | `test` | `test` |
| docs | `docs-build` (`pnpm run docs:build` → Astro/Starlight) | `docs-build` |

The `test` recipe runs the skill + wiki validator self-tests and
validators (`test_validate_skills.py`, `test_validate_wiki.py`,
`validate_skills.py`, `validate_wiki.py`), the pytest suites
(`tests/python`, `tests/shared/python`, `tests/fanout/python`,
`tests/schemas/python`, `tests/hard-cheese/python`,
`tests/pasteurize/python`, `tests/wheypoint/python`), the JS suite
(`node --test tests/js`), and the bats suites
(`tests/bash/test_install.bats`, the fan-out bats) (`justfile:15-31`).

Every leg of the gate is Python, JS, or bash. The gate carried one Rust
leg — `just test-skill-overlap`, `cargo test` against
`tools/skill-overlap/` — until the overlap ratchet was retired
([[adr/skill-overlap-ratchet-005]]); a Rust toolchain is no longer a
prerequisite for running `just check` to completion.

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



### Dead-code gate

`just lint-py-dead-code` runs Vulture 2.16 over `src`, `scripts`, `.github/scripts`, and `tests` with no broad decorator ignores or path excludes. Findings fail unless they are explicitly classified by exact owner-qualified identities (schema Enum members, attrs fields, autouse `pytest.fixture`, or the small stdlib callback override set) or carry a definition-site `# noqa: V103` annotation for generated validator methods. This recipe is wired into CI alongside the local `just check` gate.

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

Every Python-backed skill ships exactly one same-named Shiv archive at
`skills/<skill>/scripts/<skill>.pyz`; there is no `common.pyz` or
`COMMON_CONSUMERS` fan-out.[^1] Runtime source lives under
`src/easy_cheese/`: each skill application depends on the cohesive shared
distribution and the published schemas package through package metadata.[^2]

`just bundle` rebuilds every archive from PEP 517 wheels in a private
wheelhouse. `requirements/runtime.txt` is the sole committed hash lock and
admits only external wheels. Each build uses pip's resolved-install report to
write the complete external-plus-internal closure beside the temporary
wheelhouse, then gives that ephemeral file to Shiv under `--require-hashes`.
Locally built wheel hashes are verified during assembly but never versioned.[^3]

The archives are committed deployment artifacts. `build-pyz.yml` rebuilds them
in a read-only CI job, compares canonical archive-member content against
`HEAD`, and runs isolation tests; it never commits generated changes. Changes
to runtime source, build inputs, the external runtime lock, manifests, or
committed archives must therefore be followed by `just bundle` before
publication.[^4]

See the [bundle pipeline](./architecture/pyz-bundling-pipeline.md) and
[skill Python bundle doctrine](./architecture/skill-python-bundle-doctrine.md)
for the dependency and purity contracts.

[^1]: scripts/build_pyz.py
[^2]: pyproject.toml; src/easy_cheese/shared; src/easy_cheese/skills
[^3]: scripts/build_pyz.py; requirements/runtime.txt
[^4]: .github/workflows/build-pyz.yml; scripts/check_bundles.py

## CI workflows

Under `.github/workflows/`:

| Workflow | Trigger | Does |
|---|---|---|
| `validate.yml` | push main, all PRs | frontmatter validation, pytest, install.sh bats + smoke, lint |
| `build-pyz.yml` | PRs + push main (runtime source, bundle build/check code, locks, manifests, committed archives) | rebuild committed targets, verify canonical archive-member content against `HEAD`, and run bundle isolation tests — never commits |
| `release.yml` | tag `v[0-9]*` | stage slim tree, force-push `release` branch, GitHub release |
| `publish-pypi.yml` | push main touching `pyproject.toml`, dispatch | publish `easy-cheese-schemas` to PyPI |
| `docs.yml` | push/PR on docs paths, dispatch | `pnpm run docs:build` (Astro/Starlight), deploy Pages on main |
| `docs-retry.yml` | `docs` workflow_run failure | auto re-run failed `docs` jobs on main, up to 3 attempts |
| `codeql.yml` | PRs, push main, weekly | CodeQL on python + actions |
| `dependency-review.yml` | PRs to main | block vulnerable / disallowed-license deps |
| `scorecard.yml` | push main, weekly | OpenSSF Scorecard → SARIF |
| `copilot-review.yml` | PR opened/reopened/ready | add Copilot as reviewer |

### Prerequisites

`just`, `uv` (for `uvx ruff`), plus `yamllint`, `yamlfmt`,
`markdownlint-cli2`, `shellcheck`, and `bats` — see `README.md` for
install hints (`AGENTS.md:18-21`).
