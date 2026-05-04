# easy-cheese

A lightweight, skills-only cheese workflow for agents that support `gh skill`-style discovery. The workflow is adapted from `paulnsorensen/cheese-flow.git` while keeping this repository portable: no required delegation setup, generated harness files, or mandatory MCP configuration.

## Skill layout

This repository uses the hierarchical skill discovery conventions documented by `gh skill`:

- `skills/<name>/SKILL.md` for a top-level skill
- `skills/<scope>/<name>/SKILL.md` for a scoped sub-skill under that top-level skill

Each top-level skill is an orchestrator. Each workflow step or review dimension lives in its own sub-skill with explicit tool preferences and fallbacks.

## Top-level skills

| Skill path | Command | Purpose |
| --- | --- | --- |
| `skills/briesearch/SKILL.md` | `/briesearch` | Research technical questions across docs, web, codebase, and GitHub examples with explicit source sub-skills. |
| `skills/mold/SKILL.md` | `/mold` | Shape a fuzzy idea into a grounded spec through mode, evidence, seam, approval, and artifact sub-skills. |
| `skills/culture/SKILL.md` | `/culture` | No-write thinking space for architecture, trade-offs, and ambiguous problems decomposed into dialogue sub-skills. |
| `skills/cook/SKILL.md` | `/cook` | Implement a clear spec with cheese-flow-inspired contract, cut, implement, taste-test, press, assertion-review, and package sub-skills. |
| `skills/press/SKILL.md` | `/press` | Harden cooked changes through contract, test map, gap analysis, focused tests, fixes, checks, and report sub-skills. |
| `skills/age/SKILL.md` | `/age` | Lightweight staff-engineer review across correctness, security, encapsulation, spec, complexity, deslop, assertions, and NIH sub-skills. |
| `skills/cure/SKILL.md` | `/cure` | Fix selected review findings through load, selection, apply, validate, re-age, and shipping report sub-skills. |

Suggested flow:

```text
/briesearch → /mold → /culture → /cook → /press → /age → /cure
```

Use only the skills you need. A clear implementation request can go straight to `/cook`; a no-write design discussion should stay in `/culture`.

## Sub-skills

Preview or install sub-skills by exact path so the hierarchy is unambiguous.

| Sub-skill path | Command |
| --- | --- |
| `skills/age/assertions/SKILL.md` | `/age/assertions` |
| `skills/age/complexity/SKILL.md` | `/age/complexity` |
| `skills/age/correctness/SKILL.md` | `/age/correctness` |
| `skills/age/deslop/SKILL.md` | `/age/deslop` |
| `skills/age/encapsulation/SKILL.md` | `/age/encapsulation` |
| `skills/age/nih/SKILL.md` | `/age/nih` |
| `skills/age/orient/SKILL.md` | `/age/orient` |
| `skills/age/security/SKILL.md` | `/age/security` |
| `skills/age/spec/SKILL.md` | `/age/spec` |
| `skills/age/synthesize/SKILL.md` | `/age/synthesize` |
| `skills/briesearch/classify/SKILL.md` | `/briesearch/classify` |
| `skills/briesearch/gather/SKILL.md` | `/briesearch/gather` |
| `skills/briesearch/handoff/SKILL.md` | `/briesearch/handoff` |
| `skills/briesearch/source-plan/SKILL.md` | `/briesearch/source-plan` |
| `skills/briesearch/synthesize/SKILL.md` | `/briesearch/synthesize` |
| `skills/cook/assertion-review/SKILL.md` | `/cook/assertion-review` |
| `skills/cook/contract/SKILL.md` | `/cook/contract` |
| `skills/cook/cut/SKILL.md` | `/cook/cut` |
| `skills/cook/implement/SKILL.md` | `/cook/implement` |
| `skills/cook/package-report/SKILL.md` | `/cook/package-report` |
| `skills/cook/press-handoff/SKILL.md` | `/cook/press-handoff` |
| `skills/cook/taste-test/SKILL.md` | `/cook/taste-test` |
| `skills/culture/constraints/SKILL.md` | `/culture/constraints` |
| `skills/culture/light-evidence/SKILL.md` | `/culture/light-evidence` |
| `skills/culture/restate/SKILL.md` | `/culture/restate` |
| `skills/culture/summary/SKILL.md` | `/culture/summary` |
| `skills/culture/tradeoffs/SKILL.md` | `/culture/tradeoffs` |
| `skills/cure/apply/SKILL.md` | `/cure/apply` |
| `skills/cure/load/SKILL.md` | `/cure/load` |
| `skills/cure/re-age/SKILL.md` | `/cure/re-age` |
| `skills/cure/select/SKILL.md` | `/cure/select` |
| `skills/cure/ship-report/SKILL.md` | `/cure/ship-report` |
| `skills/cure/validate/SKILL.md` | `/cure/validate` |
| `skills/mold/approval/SKILL.md` | `/mold/approval` |
| `skills/mold/artifacts/SKILL.md` | `/mold/artifacts` |
| `skills/mold/dialogue/SKILL.md` | `/mold/dialogue` |
| `skills/mold/ground/SKILL.md` | `/mold/ground` |
| `skills/mold/mode-route/SKILL.md` | `/mold/mode-route` |
| `skills/mold/options/SKILL.md` | `/mold/options` |
| `skills/mold/seams/SKILL.md` | `/mold/seams` |
| `skills/press/add-tests/SKILL.md` | `/press/add-tests` |
| `skills/press/corrective-fixes/SKILL.md` | `/press/corrective-fixes` |
| `skills/press/gap-analysis/SKILL.md` | `/press/gap-analysis` |
| `skills/press/map-tests/SKILL.md` | `/press/map-tests` |
| `skills/press/read-contract/SKILL.md` | `/press/read-contract` |
| `skills/press/report/SKILL.md` | `/press/report` |
| `skills/press/run-checks/SKILL.md` | `/press/run-checks` |

## Tool preferences and fallbacks

Every sub-skill includes a tool table. Preferred tools are optional; when unavailable, the skill should say so once, use the fallback, and lower confidence only when evidence quality or edit precision is affected.

| Tool | Helps with | Fallback |
| --- | --- | --- |
| `sg` | Structural code search | `ripgrep`, `find`, targeted reads |
| tilth | Precise read/search/edit and dependency context | harness read/edit tools or patches |
| Context7 | Library and API documentation | repo docs, package docs, vendor pages, web search |
| Tavily | Current web/vendor research | generic web search or user-supplied sources |
| code review graph | Review impact radius and dependency/caller context | import searches, caller searches, tests |
| Serena or LSP | Semantic navigation and symbol understanding | `sg`, `ripgrep`, targeted reads |
| `ripgrep` | Fast text search | `grep`, `find`, editor search |
| `gh` | GitHub issues, PRs, checks, examples | local git commands or user-provided links/logs |
| `delta` | Readable diffs | plain `git diff` |
| mergiraf | Structured merge conflict resolution | manual conflict resolution plus tests |
| `jq` | JSON inspection for reports or tool output | manual inspection |
| `fd` | Fast file discovery | `find` |
| `just` | Project task discovery | package scripts or documented commands |

## Preview or install

Preview a top-level skill:

```sh
gh skill preview paulnsorensen/easy-cheese briesearch
gh skill preview paulnsorensen/easy-cheese cook
gh skill preview paulnsorensen/easy-cheese age
```

Preview a sub-skill:

```sh
gh skill preview paulnsorensen/easy-cheese skills/cook/cut
gh skill preview paulnsorensen/easy-cheese skills/cook/taste-test
gh skill preview paulnsorensen/easy-cheese skills/age/security
```

Install examples:

```sh
gh skill install paulnsorensen/easy-cheese cook
gh skill install paulnsorensen/easy-cheese skills/cook/cut
gh skill install paulnsorensen/easy-cheese skills/age/correctness
```

## Validate for publishing

When using a GitHub CLI version that includes `gh skill`, validate locally with:

```sh
gh skill publish --dry-run
```

Publishing expects each `SKILL.md` to include YAML frontmatter with at least `name` and `description`, and the `name` must match its directory name.
