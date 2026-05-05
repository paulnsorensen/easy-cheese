# easy-cheese

A lightweight, skills-only adaptation of [`paulnsorensen/cheese-flow`](https://github.com/paulnsorensen/cheese-flow) that ships only Agent Skills — no agents, no compiled harness bundles, no required MCP servers. The vocabulary stays the same (mold, culture, cook, press, age, cure) so muscle memory carries over.

## Skill layout

This repo follows the [Agent Skills spec](https://agentskills.io/specification):

```
skills/
└── <skill-name>/
    ├── SKILL.md          # required: name + description + body
    ├── references/       # optional: detail pulled in on demand
    ├── scripts/          # optional: executable helpers
    └── assets/           # optional: templates / static resources
```

Each `SKILL.md` is self-contained markdown with YAML frontmatter. There are no nested sub-skills; deeper material lives in `references/<topic>.md` so the harness can load it progressively.

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

Use only the skills you need. A clear bug can go straight to `/cook`; a no-write design discussion should stay in `/culture`.

## Differences from cheese-flow

Easy Cheese is intentionally a smaller surface. Compared to upstream:

- **Skills only.** No agents, commands, eta templates, or compiled harness bundles. Each capability is a single `SKILL.md`.
- **No required MCP.** Skills suggest tools (tilth, Context7, Tavily, code-review-graph) but every step has a fallback to host-native tools.
- **`/age` drops the `precedent` dimension.** Without git history analysis as a built-in agent, that dim is unreliable in a portable skill.
- **No `/fromage`, `/fromagerie`, `/cleanup`, `/nih-audit`.** Those orchestrators live in cheese-flow proper.
- **No automatic re-age loop in `/cure`.** The skill describes the protocol; the human runs the next `/age` when ready.

If you need the full pipeline, install cheese-flow itself.

## Optional tools

Skills name preferred tools when they help, with fallbacks for portability:

| Tool | Helps with | Fallback |
| --- | --- | --- |
| tilth (MCP) | AST-aware read/search/edit and dependency context | host read/edit, `ripgrep`, patches |
| `sg` (ast-grep) | Structural pattern matching with metavariables | `ripgrep`, `find`, targeted reads |
| Context7 (MCP) | Library and API documentation | repo docs, package docs, vendor pages, web search |
| Tavily (MCP) | Current web/vendor research | host web search or user-supplied sources |
| code-review-graph (MCP) | Review impact radius and caller/dep context | import searches, caller searches, tests |
| LSP / Serena | Semantic navigation and symbol understanding | `sg`, `ripgrep`, targeted reads |
| `ripgrep` | Fast text search | `grep`, `find`, editor search |
| `gh` | GitHub issues, PRs, checks, examples | local git commands or user-provided links/logs |
| `delta` | Readable diffs | plain `git diff` |
| `mergiraf` | Structured merge conflict resolution | manual conflict resolution plus tests |
| `jq` | JSON inspection for reports or tool output | manual inspection |
| `fd` | Fast file discovery | `find` |
| `just` | Project task discovery | package scripts or documented commands |

When a preferred tool is unavailable, each skill says so once, falls back, and lowers confidence only if evidence quality suffers.

## Install

### Claude Code (plugin)

Once a `.claude-plugin/plugin.json` is added to this repo, install with:

```sh
/plugin install paulnsorensen/easy-cheese
```

### Claude Code (manual)

Copy the skills you want into your skills directory:

```sh
# Per-user
mkdir -p ~/.claude/skills
cp -r skills/age ~/.claude/skills/

# Per-project
mkdir -p .claude/skills
cp -r skills/cook .claude/skills/
```

### Other harnesses

Copy `skills/<name>/` into wherever the harness loads Agent Skills from. The format follows the [agentskills.io spec](https://agentskills.io/specification) and works in any compliant client.

## Validate

The reference validator from [`agentskills/agentskills`](https://github.com/agentskills/agentskills) checks frontmatter and naming:

```sh
skills-ref validate ./skills/age
```

Each `SKILL.md` must have YAML frontmatter with at least `name` and `description`, and `name` must match the parent directory name.
