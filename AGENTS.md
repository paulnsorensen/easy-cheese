# Agent Instructions for easy-cheese

This document is for LLMs, agents, and automation tools working in this repository.

## Single Quality Gate: `just check`

**Always run `just check` before declaring work done — before any commit, push, PR open, or hand-off.** Treat green from `just check` as the only signal that a change is shippable.

`just check` autofixes lint (markdown, yaml, python via `ruff`) and runs the full local build: skill frontmatter validation (`validate_skills.py`), shell lint, python + bash test suites, and `mkdocs build --strict`. CI runs `just ci` (same checks, no autofixes).

```bash
just check
```

Do NOT commit or push when `just check` fails. If CI fails, pull the branch locally, run `just check`, commit the autofixes, and push.

### Prerequisites

- [`just`](https://github.com/casey/just) — recipe runner
- [`uv`](https://github.com/astral-sh/uv) — `lint-py-fix` invokes `uvx ruff` (no global ruff install needed)
- `yamllint`, `yamlfmt`, `markdownlint-cli2`, `shellcheck`, `bats` — see README for install hints

## Skills in this repo

This is a skills-only collection following the [Agent Skills spec](https://agentskills.io/specification). Every change either adds, edits, or supports a skill under `skills/<name>/`.

### Workflow skills (the cheese pipeline)

| Skill | Purpose |
|---|---|
| `/cheese` | Unified entry — classifies input and routes to the right downstream skill |
| `/briesearch` | External research router (Context7, Tavily, gh, local code) |
| `/mold` | Iterative dialogue to converge a fuzzy idea into an approved spec |
| `/culture` | Deep no-write exploration of a codebase or topic |
| `/pasteurize` | Hard-bug diagnosis — feedback-loop-first investigation, regression test, minimal fix, then handoff to `/cook` |
| `/cook` | TDD-disciplined implementation of an approved spec |
| `/press` | Adversarial test hardening after `/cook` |
| `/age` | Ten-dimension code review producing a severity-grouped findings report |
| `/affinage` | Triages a PR's review comments and CI failures through the `/age` lens, routes fixes to `/cure`, posts replies |
| `/cure` | Applies selected `/age` findings as focused fixes |
| `/ultracook` | Autonomous fresh-context pipeline for high-blast-radius specs, one sub-agent per phase. The decomposer picks the mode: a decomposable 2+-curd spec fans out into parallel curds (per-curd `cook → press → age → cure` in its own worktree, harvested back, one post-merge review pass, ending in 1–N reviewable PRs); an indivisible spec runs the linear chain `cook → press → age → cure → age → cure → age`, all `--auto` |
| `/melt` | Resolves merge / rebase / cherry-pick conflicts via the structural-merge cascade |
| `/wheypoint` | Checkpoints a mid-task conversation into a durable handoff at `.cheese/notes/<slug>.md`, resumable via `/cheese --continue` |

### Tool skills (lower-level primitives)

| Skill | Purpose |
|---|---|
| `/cheez-search` | AST/LSP-aware source search via tilth MCP or an equivalent semantic backend — replaces blind grep / rg / ripgrep |
| `/cheez-read` | Fresh bounded file/directory reader via tilth MCP or equivalent native snapshot/list backend — replaces blind cat / head / tail |
| `/cheez-write` | Stale-safe anchored edit writer via tilth MCP, LSP workspace edits, AST rewrites, or equivalent native snapshot edits — replaces blind inline Edit / Write |

See `README.md` for the full workflow and the suggested skill ordering.

## Durable memory

This repo keeps a durable-knowledge wiki at `.hallouminate/wiki/`
(git-tracked, corpus `repo:easy-cheese:wiki`), separate from the
transient per-task scratch under `.cheese/` (gitignored). **Recommended
default:** after a change lands on `main` that altered durable
knowledge — architecture, protocols, conventions, or a "why this design
not that one" decision — query the wiki and update it. Routine fixes and
per-task output stay in `.cheese/`.

This is a recommended default, not a hard gate: updating the wiki
requires the [hallouminate](https://github.com/paulnsorensen/hallouminate)
MCP server. When it is unavailable, skip the update — do not hand-edit
the LanceDB-indexed tree. See `.hallouminate/wiki/wiki-conventions.md`
for the durable-vs-transient boundary and the authoring loop.

## Development notes

- Python validators in `.github/scripts/` allow only `pyyaml` and `pytest` as third-party deps — see `.github/instructions/python.instructions.md`.
- Shell scripts and bats tests follow the rules in `.github/instructions/shell.instructions.md`.
- `cheez-*` skills use the safest semantic backend available for source code: prefer tilth when present; otherwise accept equivalent native LSP/AST/anchored/stale-checking backends. Use LSP for type-grounded defs/refs/renames/code actions, `sg` for structural rewrites, batch reads/writes when possible, and treat blind shell search/view/edit as weaker fallback evidence, not an equivalent source-code backend. Optional integrations — hallouminate (repo-wiki grounding for `/mold` and `/age`) and milknado (mikado task-graph backend for `/ultracook` parallel mode) — are wired in as optional plugins per `shared/optional-plugins.md`: they degrade gracefully when absent and never block a skill run.
- SKILL.md files must pass `validate_skills.py` (YAML frontmatter validation).
- Conventional Commits format for all commits and PR titles (enforced by `validate.yml` for PRs).
- Cheese / Dune / Mad Max / LOTR / Princess Bride flavor is welcome in user-facing docs and `SKILL.md` files. Keep commit messages and YAML frontmatter neutral.
