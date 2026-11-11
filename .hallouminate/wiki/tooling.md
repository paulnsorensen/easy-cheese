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
| tests | `test` | `test` |
| docs | `docs-build` (`pnpm run docs:build` → Astro/Starlight) | `docs-build` |

The `test` recipe runs the skill + wiki validator self-tests and
validators (`test_validate_skills.py`, `test_validate_wiki.py`,
`validate_skills.py`, `validate_wiki.py`), the pytest suites
(`tests/python`, `tests/shared/python`, `tests/fanout/python`,
`tests/schemas/python`, `tests/hard-cheese/python`,
`tests/pasteurize/python`, `tests/wheypoint/python`), the JS suite
(`node --test tests/js`), the fan-out bats
suite (`tests/fanout/bash/test_pr_plan_to_branches.bats`), and
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

## Development-only prompt optimization

The prompt laboratory is an experimental repository tool, not an installed skill.
It uses direct GEPA to optimize Markdown through a custom evaluator.
DSPy is not required because the candidate is text, not a DSPy program.[^prompt-lab-fit]
The scripts and optional development dependencies stay outside every skill bundle.[^prompt-lab-code]

The evaluator checks decision-state preservation across anonymized conversation turns.
It is a behavioral proxy, not proof that an installed agent executes tools correctly.
Training and optimizer-visible validation use separate scenario families.
A third holdout remains outside optimization and requires an explicit evaluation run.
Generated candidates require human review and never update installed prompts automatically.[^prompt-lab-code]

The agent laboratory provides two outcome-graded runners.
The legacy runner uses disposable fixture copies and mutation-based tests.
It exports a candidate only when the best candidate strictly beats the seed on train plus validation.[^agent-lab-code]

### Agent Lab: bounded optimization on selected repositories

Agent Lab does not select repositories or run a continuous optimizer.
The operator selects `tasks mine --repo`, supplies a task file, and starts a bounded `optimize --runner tilth` invocation.
The tool exports candidates for review; it never changes installed skills automatically.[^agent-lab-code]

Mining reads supported GitHub author metadata and preserves trusted-author defaults, SHA pins, and test-only patches.
The current Tilth checker accepts pytest tasks and proves failure at the base and success at the fixed head.
An explicit `--lint-command` preserves the repository's lint argument vector.
Absent lint evidence fails the erosion guard; a no-op command is not valid lint evidence.[^agent-lab-mine]

Each Cook candidate builds current Wedge archives in a disposable worktree.
The plugin registers Cook and carries companion skill resources, including Press, Age, Cure, and Plate.
Candidate changes stay inside Cook's existing allowlist.[^agent-lab-build]

Tilth evaluations require exact, unique task coverage and valid diff and lint measurements.
Train and validation stay separate from the sealed holdout.
Stable task IDs separate GEPA's training and validation cache entries.
Split-local numeric IDs can reuse training scores as validation evidence.
Reflection uses authenticated `claude -p`, with tools disabled, a per-call dollar cap, and a finite timeout.
Reflection and benchmark evaluations share `--max-runs`; exhaustion writes partial results and returns a non-success status.[^agent-lab-code]

Promotion evaluates the sealed holdout on Haiku, Sonnet, and Opus.
It requires non-regressing accuracy on every model, non-dominance on both objectives, and at least one strict improvement.
Source checks and offline tests do not establish live model quality or savings.[^agent-lab-graduate]

[^prompt-lab-fit]: https://github.com/gepa-ai/optimize-anything-artifact; https://github.com/stanfordnlp/dspy/blob/main/docs/docs/diving-deeper/gepa-in-depth.md (checked 2026-09-24).
[^prompt-lab-code]: scripts/prompt_lab.py; requirements/prompt-lab.txt; tests/fixtures/prompt_lab/dataset.json; docs/prompt-lab.md.
[^agent-lab-code]: scripts/agent_lab.py:274-409,955-1131; tests/fixtures/prompt_lab/agent_tasks.json; tests/python/test_agent_lab.py; docs/prompt-lab.md.
[^agent-lab-mine]: scripts/agent_lab_mine.py:291-334; docs/prompt-lab.md:109-123.
[^agent-lab-build]: scripts/agent_lab_candidate.py:23-29,210-259; tests/python/test_agent_lab_candidate.py.
[^agent-lab-graduate]: scripts/agent_lab_scoring.py:105-134,157-220; scripts/agent_lab_tilth.py; docs/prompt-lab.md:136-159.

_Source: PR #728 repair contract and implementation · Updated: 2026-11-11 · Supersedes: fixture-only Agent Lab runtime description from 2026-09-25._

## `.pyz` archives

Each Python skill ships one executable `skills/<skill>/scripts/<skill>.pyz`.
`main` tracks no archive; `publish dist` commits them to `dist`, the default branch.
The archive contains its own skill code, shared support, CLI support, schemas, and pinned dependencies.
No launcher, sidecar lock, or first-run download is required.[^1]

`just wedge-build` runs the Wedge commit pinned in `tools/wedge/uv.lock`.
Each manifest's `source_paths` preserves package paths while excluding other skill packages.
The `runtime` group and schema dependencies define the third-party closure in `uv.lock`.[^2]

Run `just wedge-build` after a fresh clone or a change to archive inputs, then run `just check`.
`just test` builds the archives before tests execute them.
Focused test commands do not build archives; run `just wedge-build` first.
The release workflow builds the archives before release staging copies them.[^3]

See the [bundle pipeline](./architecture/pyz-bundling-pipeline.md) and
[skill Python bundle doctrine](./architecture/skill-python-bundle-doctrine.md).

[^1]: AGENTS.md; .github/workflows/publish-dist.yml; scripts/publish_dist.py
[^2]: skills/wedge.toml; skills/*/wedge.toml; pyproject.toml; uv.lock; tools/wedge/uv.lock
[^3]: justfile; tests/conftest.py; scripts/stage_release.py; .github/workflows/validate.yml; CONTRIBUTING.md

## CI workflows

Under `.github/workflows/`:

| Workflow | Trigger | Does |
|---|---|---|
| `validate.yml` | push main, all PRs, merge groups | frontmatter validation, archive build before pytest, publish checks (stage, `gh skill publish --dry-run`, archive `--help`), fan-out bats on macOS, lint |
| `publish-dist.yml` | push main, hourly schedule, dispatch | build archives from the `main` tip, append one full-tree commit to `dist` |
| `retarget-dist-prs.yml` | PRs opened against `dist` | move the PR base to `main` |
| `release.yml` | tag `v[0-9]*` | build archives, stage slim tree, force-push `release` branch, GitHub release |
| `publish-pypi.yml` | push main touching `pyproject.toml`, dispatch | publish `easy-cheese-schemas` to PyPI |
| `docs.yml` | push/PR on docs paths, dispatch | `pnpm run docs:build` (Astro/Starlight), deploy Pages on main |
| `docs-retry.yml` | `docs` workflow_run failure | auto re-run failed `docs` jobs on main, up to 3 attempts |
| `skill-overlap.yml` | PRs on `skills/**/*.md` + tools, weekly cron, dispatch | semantic skill-overlap ratchet (`calibrate` / `report` / `check`) |
| `codeql.yml` | PRs, push main, weekly | CodeQL on python + actions |
| `dependency-review.yml` | PRs to main | block vulnerable / disallowed-license deps |
| `scorecard.yml` | weekly, branch protection changes | OpenSSF Scorecard → SARIF (default branch only) |

### Prerequisites

`just`, `uv` (for `uvx ruff`), plus `yamllint`, `yamlfmt`,
`markdownlint-cli2`, and `bats` — see `README.md` for
install hints (`AGENTS.md:18-21`).

_Source: [PR #729](https://github.com/paulnsorensen/easy-cheese/pull/729), approved A correction; `scripts/install.sh` removal (npx-only install) · Updated: 2026-10-18 · Supersedes: runtime loaders, release-only archive assets, temporary test archives, and the separate archive workflow._
