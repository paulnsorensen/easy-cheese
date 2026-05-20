# Agent Instructions for easy-cheese

This document is for LLMs, agents, and automation tools working in this repository.

## Single Quality Gate: `just check`

**Always run `just check` before declaring work done — before any commit, push, PR open, or hand-off.** Treat green from `just check` as the only signal that a change is shippable.

`just check` autofixes lint (markdown, yaml, python via `ruff`) and runs the full local build: skill frontmatter validation (`skills-ref`), shell lint, python + bash test suites, and `mkdocs build --strict`. CI runs `just ci` (same checks, no autofixes).

```bash
just check
```

Do NOT commit or push when `just check` fails. If CI fails, pull the branch locally, run `just check`, commit the autofixes, and push.

### Prerequisites

- [`just`](https://github.com/casey/just) — recipe runner
- [`uv`](https://github.com/astral-sh/uv) — `lint-py-fix` invokes `uvx ruff` (no global ruff install needed)
- [`skills-ref`](https://github.com/agentskills/agentskills) — `pip install skills-ref` or `uv tool install skills-ref`
- `yamllint`, `yamlfmt`, `markdownlint-cli2`, `shellcheck`, `bats` — see README for install hints

## Skills in this repo

This is a skills-only collection following the [Agent Skills spec](https://agentskills.io/specification). Every change either adds, edits, or supports a skill under `skills/<name>/`.

### Workflow skills (the cheese pipeline)

| Skill | Purpose |
|---|---|
| `/cheese` | Unified entry — classifies input and routes to the right downstream skill |
| `/mold` | Iterative dialogue to converge a fuzzy idea into an approved spec |
| `/culture` | Deep no-write exploration of a codebase or topic |
| `/cook` | TDD-disciplined implementation of an approved spec |
| `/press` | Adversarial test hardening after `/cook` |
| `/age` | Ten-dimension code review producing a severity-grouped findings report |
| `/cure` | Applies selected `/age` findings as focused fixes |
| `/melt` | Resolves merge / rebase / cherry-pick conflicts via the structural-merge cascade |
| `/briesearch` | External research router (Context7, Tavily, gh, local code) |
| `/cheese-factory` | Large-feature orchestrator: decomposes an approved spec into seed + parallel curds + wiring, fans out per-curd `/cook → /press → /age → /cure`, runs post-merge review, ends in 1–N reviewable PRs |

### Tool skills (lower-level primitives)

| Skill | Purpose |
|---|---|
| `/cheez-search` | AST-aware search via tilth MCP — replaces grep / rg / ripgrep |
| `/cheez-read` | Smart-outlining file reader via tilth MCP — replaces cat / head / tail |
| `/cheez-write` | Batched edit writer via tilth MCP — replaces inline Edit / Write |
| `/ultracook` | Composite workflow chaining `/cook` → `/press` → `/age` → `/cure` |

See `README.md` for the full workflow and the suggested skill ordering.

## Development notes

- Python validators in `.github/scripts/` allow only `pyyaml` and `pytest` as third-party deps — see `.github/instructions/python.instructions.md`.
- Shell scripts and bats tests follow the rules in `.github/instructions/shell.instructions.md`.
- `cheez-*` skills require [tilth MCP](https://github.com/paulnsorensen/tilth) and hard-fail without it. Every other skill stays portable and degrades to host-native tools.
- SKILL.md files must pass `validate_skills.py` (YAML frontmatter validation).
- Conventional Commits format for all commits and PR titles (enforced by `validate.yml` for PRs).
- Cheese / Dune / Mad Max / LOTR / Princess Bride flavor is welcome in user-facing docs and `SKILL.md` files. Keep commit messages and YAML frontmatter neutral.
