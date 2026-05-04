# easy-cheese

A lightweight, skills-only cheese workflow for agents that support `gh skill`-style discovery. It keeps the cheese-flow vocabulary while avoiding required delegation setup, generated harness files, or mandatory MCP setup.

## Skill layout

This repository uses the skill discovery conventions documented by `gh skill`:

- `skills/<name>/SKILL.md` for a top-level skill
- `skills/<scope>/<name>/SKILL.md` for a namespaced, hierarchical skill when a future skill needs one

Each skill is self-contained markdown with portable frontmatter. The harness decides how to execute the instructions.

## Skills

| Skill path | Command | Purpose |
| --- | --- | --- |
| `skills/briesearch/SKILL.md` | `/briesearch` | Research technical questions across docs, web, codebase, and GitHub examples with fallbacks. |
| `skills/mold/SKILL.md` | `/mold` | Shape fuzzy ideas into grounded specs or issue drafts. |
| `skills/culture/SKILL.md` | `/culture` | No-write rubber-ducking and architecture exploration. |
| `skills/cook/SKILL.md` | `/cook` | Implement clear specs or focused requests with scoped edits and tests. |
| `skills/press/SKILL.md` | `/press` | Harden cooked changes with coverage, assertion, and boundary checks. |
| `skills/age/SKILL.md` | `/age` | Review diffs across staff-engineer dimensions and produce evidence-backed findings. |
| `skills/cure/SKILL.md` | `/cure` | Fix selected findings, validate, and prepare the branch for shipping. |

Suggested flow:

```text
/briesearch → /mold → /culture → /cook → /press → /age → /cure
```

Use only the skills you need. For example, a clear bug can go straight to `/cook`, while a no-write design discussion should stay in `/culture`.

## Optional tools

The skills suggest these tools when available, but none are required:

| Tool | Helps with | Fallback |
| --- | --- | --- |
| `sg` | Structural code search | `ripgrep`, `find`, targeted reads |
| tilth | Precise read/search/edit and dependency context | harness read/edit tools, patches, import searches |
| Context7 | Library and API documentation | repo docs, package docs, vendor pages, web search |
| Tavily | Current web/vendor research | generic web search or user-supplied sources |
| code review graph | Review impact radius and dependency/caller context | import searches, caller searches, tests, local history |
| Serena or LSP | Semantic navigation and symbol understanding | `sg`, `ripgrep`, targeted reads |
| `ripgrep` | Fast text search | `grep`, `find`, editor search |
| `gh` | GitHub issues, PRs, checks, examples | local git commands or user-provided links/logs |
| `delta` | Readable diffs | plain `git diff` |
| mergiraf | Structured merge conflict resolution | manual conflict resolution plus tests |
| `jq` | JSON inspection for reports or tool output | manual inspection |
| `fd` | Fast file discovery | `find` |
| `just` | Project task discovery | package scripts or documented commands |

If a preferred tool is unavailable, each skill should say so once, use the fallback, and lower confidence only when evidence quality is affected.

## Preview or install

Preview a skill before installing it:

```sh
gh skill preview paulnsorensen/easy-cheese briesearch
gh skill preview paulnsorensen/easy-cheese mold
gh skill preview paulnsorensen/easy-cheese culture
gh skill preview paulnsorensen/easy-cheese cook
gh skill preview paulnsorensen/easy-cheese press
gh skill preview paulnsorensen/easy-cheese age
gh skill preview paulnsorensen/easy-cheese cure
```

Install a skill:

```sh
gh skill install paulnsorensen/easy-cheese briesearch
gh skill install paulnsorensen/easy-cheese mold
gh skill install paulnsorensen/easy-cheese culture
gh skill install paulnsorensen/easy-cheese cook
gh skill install paulnsorensen/easy-cheese press
gh skill install paulnsorensen/easy-cheese age
gh skill install paulnsorensen/easy-cheese cure
```

## Validate for publishing

When using a GitHub CLI version that includes `gh skill`, validate locally with:

```sh
gh skill publish --dry-run
```

Publishing expects each `SKILL.md` to include YAML frontmatter with at least `name` and `description`, and the `name` should match its directory name.
