# easy-cheese

A lightweight, skills-only adaptation of [`paulnsorensen/cheese-flow`](https://github.com/paulnsorensen/cheese-flow) that ships only Agent Skills — no agents, no compiled harness bundles, and no repo-wide MCP requirement for the workflow skills. The vocabulary stays the same (mold, culture, cook, press, age, cure) so muscle memory carries over.

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

### Workflow skills

| Skill path | Command | Purpose |
| --- | --- | --- |
| `skills/briesearch/SKILL.md` | `/briesearch` | Research technical questions across docs, web, codebase, and GitHub examples with confidence-capped synthesis. |
| `skills/mold/SKILL.md` | `/mold` | Shape fuzzy ideas into grounded specs through dialogue, validate cycles, and a two-key handshake. |
| `skills/culture/SKILL.md` | `/culture` | No-write rubber-ducking and architecture exploration. Hard invariant: writes nothing. |
| `skills/cook/SKILL.md` | `/cook` | Implement clear specs via cut → cook → taste-test with scoped edits and tests. |
| `skills/press/SKILL.md` | `/press` | Harden cooked changes with coverage, assertion, and boundary checks. |
| `skills/age/SKILL.md` | `/age` | Review diffs across eight staff-engineer dimensions and produce a stake-grouped findings report. |
| `skills/cure/SKILL.md` | `/cure` | Fix user-selected findings, validate, and prepare the branch for shipping. |

### Tool skills

The workflow skills can delegate code search, reading, and editing to these MCP-backed skills when tilth is available:

| Skill path | Command | Purpose |
| --- | --- | --- |
| `skills/cheez-search/SKILL.md` | `/cheez-search` | AST-aware code/text/regex/caller search via tilth MCP. Replaces grep / rg / find. |
| `skills/cheez-read/SKILL.md` | `/cheez-read` | Smart file/directory reading with hash anchors via tilth MCP. Replaces cat / head / tail / ls. |
| `skills/cheez-write/SKILL.md` | `/cheez-write` | Hash-anchored, surgical edits via tilth MCP. Never rewrites whole files. |

The cheez-* skills require tilth MCP and hard-fail when it is unavailable rather than fall back to host tools. Workflow skills remain portable by falling back directly to host-native tools when they are not using cheez-*.

#### cheez-* router protocol

The three cheez-* skills are designed to chain. The standard sequence:

1. **`/cheez-search`** — locate the symbol, caller, content match, or file. AST-aware; replaces grep/rg/find.
2. **`/cheez-read`** — read the target file or section to capture hash anchors. Smart-outlines large files; replaces cat/head/tail/ls.
3. **`/cheez-write`** — apply hash-anchored edits with the anchors from step 2. Surgical; rejects on hash mismatch.

Workflow skills (`/cook`, `/age`, `/cure`) call into this chain when they need code intelligence. A skill should never search-then-edit without reading in between — the read is what produces the anchors that make the edit safe.

#### Installing tilth MCP

The cheez-* skills require [tilth](https://github.com/paulnsorensen/tilth) installed as an MCP server in your harness. tilth ships a one-shot installer:

```sh
# Install tilth CLI (one-time)
cargo install tilth        # or: brew install paulnsorensen/tap/tilth

# Register tilth as an MCP server in Claude Code (with edit mode for cheez-write)
tilth install claude-code --edit
```

Drop the `--edit` flag if you only want read/search — `cheez-write` needs edit mode to expose the `tilth_edit` MCP tool. Other supported hosts (cursor, vscode, claude-desktop, opencode, gemini, codex, zed, …) follow the same pattern: `tilth install <host> --edit`.

After install, restart your harness and confirm the tools appear:

- `mcp__tilth__tilth_search`
- `mcp__tilth__tilth_read`
- `mcp__tilth__tilth_files`
- `mcp__tilth__tilth_deps`
- `mcp__tilth__tilth_edit` (only with `--edit`)

If those don't show up, the cheez-* skills will hard-fail with "tilth MCP server is not loaded" instead of silently falling back to host tools.

### Suggested flow

```text
/briesearch → /mold → /culture → /cook → /press → /age → /cure
```

Use only the skills you need. A clear bug can go straight to `/cook`; a no-write design discussion should stay in `/culture`.

## Differences from cheese-flow

Easy Cheese is intentionally a smaller surface. Compared to upstream:

- **Skills only.** No agents, commands, eta templates, or compiled harness bundles. Each capability is a single `SKILL.md`.
- **No repo-wide MCP requirement.** Workflow skills suggest tools (tilth, Context7, Tavily, code-review-graph) but have host-native fallbacks. The cheez-* tool skills are the exception: they require tilth MCP by design.
- **`/age` drops the `precedent` dimension.** Without git history analysis as a built-in agent, that dim is unreliable in a portable skill.
- **No `/fromage`, `/fromagerie`, `/cleanup`, `/nih-audit`.** Those orchestrators live in cheese-flow proper.
- **No automatic re-age loop in `/cure`.** The skill describes the protocol; the human runs the next `/age` when ready.

If you need the full pipeline, install cheese-flow itself.

## Optional tools

Workflow skills name preferred tools when they help, with fallbacks for portability. Tool skills can be stricter when their purpose is to enforce a specific tool protocol.

| Tool | Helps with | Fallback |
| --- | --- | --- |
| tilth (MCP) | AST-aware read/search/edit and dependency context | Required for cheez-*; workflow skills can bypass cheez-* and use host read/edit, `ripgrep`, patches |
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

When a preferred tool is unavailable, workflow skills say so once, fall back, and lower confidence only if evidence quality suffers. The cheez-* skills stop instead because tilth is their compatibility requirement.

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
