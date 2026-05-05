# 🧀 easy-cheese 🧀

> _"The cheese must flow."_

A portable, skills-only toolkit of Agent Skills for shaping ideas, implementing them, and reviewing the result. No agents, no compiled harness bundles, no repo-wide MCP requirement — just self-contained `SKILL.md` files that any [Agent Skills](https://agentskills.io/specification)-compatible harness can load. The vocabulary (mold, culture, cook, press, age, cure) reads as a workflow you can dip into anywhere.

## Why cheese? Two reasons

1. **Modeled after the gaming slang term "cheese."** The term traces back to early fighting-game culture in the late 1980s and early 1990s — Street Fighter II players coined "cheesy" wins to describe victories pulled off with cheap, repeatable, low-skill tactics (corner-trap fireball spam, throw loops, AI-pattern exploits). It spread from fighting games to RTS rush builds (StarCraft "cheese rushes"), to speedrun glitch routes, to MOBA cheese picks — anywhere a player gets a disproportionately good result for very little effort. That is exactly the design center of easy-cheese: the primary tenets are **correctness, token efficiency, and quality** — _cheap and easy_ in the best sense. Maximum result, minimum spend.
2. **What's life without whimsy?** 🧀

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
| `skills/cheese/SKILL.md` | `/cheese` | Unified entry point. Classifies any input (idea, spec path, PR, stack trace, file path), announces the routing decision, and gates dispatch behind `AskUserQuestion`. Never auto-invokes. |
| `skills/briesearch/SKILL.md` | `/briesearch` | Research technical questions across docs, web, codebase, and GitHub examples with confidence-capped synthesis. |
| `skills/mold/SKILL.md` | `/mold` | Shape fuzzy ideas into grounded specs through dialogue, validate cycles, and a two-key handshake. |
| `skills/culture/SKILL.md` | `/culture` | No-write rubber-ducking and architecture exploration. Hard invariant: writes nothing. |
| `skills/cook/SKILL.md` | `/cook` | Implement clear specs via cut → cook → taste-test with scoped edits and tests. |
| `skills/press/SKILL.md` | `/press` | Harden cooked changes with coverage, assertion, and boundary checks. |
| `skills/age/SKILL.md` | `/age` | Review diffs across eight staff-engineer dimensions and produce a stake-grouped findings report. |
| `skills/cure/SKILL.md` | `/cure` | Fix user-selected findings, validate, and prepare the branch for shipping. |
| `skills/melt/SKILL.md` | `/melt` | Resolve merge / rebase / cherry-pick conflicts via the structural cascade (mergiraf → rerere → kdiff3) with batch, pick-side, and lockfile helpers. |

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

##### Tool redirection map

If you'd reach for one of these on a code task, route through cheez-* instead:

| If you'd run... | Use this skill | Why |
| --- | --- | --- |
| `grep`, `rg`, `ripgrep`, `ag`, `ack` | `/cheez-search` | AST-aware; ranks definitions over usages, filters comments/strings. |
| `find`, `fd` (by name pattern, code work) | `/cheez-read` (`tilth_files`) | Token estimates and `.gitignore` filtering for free. |
| `ast-grep` / `sg` (for name-shaped queries) | `/cheez-search` | `sg` is reserved for structural metavariable patterns tilth can't express. |
| LSP "find references" / "find definition" (manual) | `/cheez-search` | Same answer, no IDE round-trip; falls through to LSP under the hood when needed. |
| `cat`, `head`, `tail`, `less`, `more`, `bat` | `/cheez-read` | Hash anchors + outline-vs-full token budgeting. |
| `ls`, `tree`, `eza` (code dirs) | `/cheez-read` (`tilth_files`) | Token estimates; respects `.gitignore`. |
| `Read`, `Glob` (host tools, code paths) | `/cheez-read` | Bypasses session deduplication and emits no anchors. |
| `sed`, `awk`, `perl -i` | `/cheez-write` | No hash-mismatch safety; silent races on concurrent writes. |
| `patch` (apply diff to code) | `/cheez-write` | Anchored range edits are the safe equivalent. |
| `tee`, `>`, `>>` (overwrite/append code files) | `/cheez-write` | Same — no anchors, no mismatch detection. |
| `Edit`, `Write` (host tools, code) | `/cheez-write` | `tilth_edit` is the only edit path with hash-anchor safety. |
| `sg --rewrite` (codemod across N files) | `/cheez-write` | Sanctioned escape from cheez-write for structural codemods; `tilth_edit` stays the default for single-block edits. |

Outside code work (e.g. `find -mtime`, `ls /tmp`, log inspection with `tail -f`, JSON munging with `jq`) the host tools are still the right call. The redirection rule is: **anything that touches source code goes through cheez-***.

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
/cheese  ──►  classify intent
   ├─ need info / external evidence  ──►  /briesearch
   ├─ rubber-duck only               ──►  /culture
   ├─ fuzzy / multi-module idea       ──►  /mold        ──►  /cook  ──►  /press  ──►  /age  ──►  /cure
   ├─ clear, scoped ask               ──►  /cook        ──►  /press  ──►  /age   ──►  /cure
   ├─ debugging task                  ──►  /culture     ──►  /cook   ──►  /press ──►  /age  ──►  /cure
   └─ review only                     ──►  /age         ──►  /cure
```

`/cheese` is the front door. It inspects whatever you drop in (idea, spec path, PR ref, stack trace, file path), announces its routing decision, and waits for explicit confirmation before any downstream skill runs. Use it directly, or skip it when you already know the destination — a clear bug can go straight to `/cook`, a no-write design discussion stays in `/culture`. `/melt` cuts in whenever a merge step blocks `/cook` or `/cure`.

## Scope

Easy-cheese is intentionally a small surface. What that means in practice:

- **Skills only.** No agents, commands, eta templates, or compiled harness bundles. Each capability is a single `SKILL.md`.
- **No repo-wide MCP requirement.** Workflow skills suggest tools (tilth, Context7, Tavily, code-review-graph) but have host-native fallbacks. The cheez-* tool skills are the exception: they require tilth MCP by design.
- **`/age` runs eight dimensions, not nine.** Without git history analysis as a built-in agent, the `precedent` dimension is unreliable in a portable skill, so it's omitted.
- **No orchestrator skills** (no large-feature decomposition, no PR-rescue convoy, no whole-repo NIH audit). Each skill is a single, scoped step a human can drive.
- **No automatic re-age loop in `/cure`.** The skill describes the protocol; the human runs the next `/age` when ready.

## Optional tools

Workflow skills name preferred tools when they help, with fallbacks for portability. Tool skills can be stricter when their purpose is to enforce a specific tool protocol.

| Tool | Helps with | Fallback |
| --- | --- | --- |
| tilth (MCP) | AST-aware read/search/edit and dependency context | Required for cheez-\*; workflow skills can bypass cheez-\* and use host read/edit, `ripgrep`, patches |
| `sg` (ast-grep) | Structural pattern matching and codemods (`sg --rewrite`) with metavariables | `ripgrep`, `find`, targeted reads; `tilth_edit` for non-structural edits |
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
