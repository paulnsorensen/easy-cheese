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

See [Installing MCP servers → tilth](#tilth-required-for-cheez--skills) below for full instructions.

If those tools don't show up after install, the cheez-* skills will hard-fail with "tilth MCP server is not loaded" instead of silently falling back to host tools.

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

### gh skill (recommended)

Requires [GitHub CLI](https://cli.github.com) v2.90.0 or later with the `gh skill` command.

Install all skills interactively — browse what's available and pick what you want:

```sh
gh skill install paulnsorensen/easy-cheese
```

Install every skill in one shot:

```sh
gh skill install paulnsorensen/easy-cheese --all
```

Install one specific skill by name:

```sh
gh skill install paulnsorensen/easy-cheese cook
```

Pin to a specific release tag or commit SHA for reproducibility:

```sh
gh skill install paulnsorensen/easy-cheese cook@v1.2.0
gh skill install paulnsorensen/easy-cheese cook@abc123def
```

Control which agent and scope to install into:

```sh
# User-wide (default)
gh skill install paulnsorensen/easy-cheese --agent claude-code --scope user

# Committed into the current project repo
gh skill install paulnsorensen/easy-cheese --agent claude-code --scope repository
```

Supported `--agent` values include `copilot`, `claude-code`, `cursor`, `codex`, `gemini`, and others. Omit `--agent` to use the harness auto-detected from your environment.

Preview a skill's content before committing to an install:

```sh
gh skill preview paulnsorensen/easy-cheese cook
```

Keep installed skills up to date:

```sh
gh skill update --all
```

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

## Installing MCP servers

The cheez-* tool skills and several workflow skills benefit from MCP servers. Install the ones you need.

### tilth (required for cheez-* skills)

[tilth](https://github.com/paulnsorensen/tilth) provides AST-aware code search, smart file reading, and hash-anchored edits. Required by `/cheez-search`, `/cheez-read`, and `/cheez-write`.

```sh
# Install tilth CLI
cargo install tilth        # via Cargo (Rust)
brew install paulnsorensen/tap/tilth  # via Homebrew (macOS/Linux)

# Register as an MCP server — include --edit only if you plan to use cheez-write
tilth install claude-code --edit   # Claude Code
tilth install cursor --edit        # Cursor
tilth install vscode --edit        # VS Code
tilth install codex --edit         # Codex CLI
tilth install gemini --edit        # Gemini CLI
tilth install zed --edit           # Zed
```

After registering, restart your harness and confirm these tools appear:

- `mcp__tilth__tilth_search`
- `mcp__tilth__tilth_read`
- `mcp__tilth__tilth_files`
- `mcp__tilth__tilth_deps`
- `mcp__tilth__tilth_edit` (only with `--edit`)

### Context7 (library documentation)

[Context7](https://github.com/upstash/context7) fetches up-to-date, version-specific library docs into your session. Used by `/briesearch` and `/cook` when available.

**Claude Code:**

```sh
claude mcp add context7 -- npx -y @upstash/context7-mcp@latest
```

**Other harnesses** — add to your MCP config file:

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    }
  }
}
```

For higher rate limits, get a free API key at [context7.com](https://context7.com) and append `--api-key YOUR_API_KEY` to the `args` array. A keyless hosted option is also available:

```json
{
  "mcpServers": {
    "context7": {
      "url": "https://mcp.context7.com/mcp"
    }
  }
}
```

Requires Node.js v18+.

### Tavily (web search)

[Tavily](https://github.com/tavily-ai/tavily-mcp) provides real-time web search and content extraction. Used by `/briesearch` when available.

Get a free API key at [tavily.com](https://tavily.com), then:

**Claude Code:**

```sh
claude mcp add tavily -- npx -y tavily-mcp
```

Set your key in the environment or pass it inline:

```sh
TAVILY_API_KEY=your-key npx -y tavily-mcp
```

**Other harnesses** — add to your MCP config file:

```json
{
  "mcpServers": {
    "tavily": {
      "command": "npx",
      "args": ["-y", "tavily-mcp"],
      "env": {
        "TAVILY_API_KEY": "your-key"
      }
    }
  }
}
```

Requires Node.js v18+.

### code-review-graph (review impact radius)

[code-review-graph](https://github.com/tirth8205/code-review-graph) builds a call graph of your codebase and exposes it as MCP tools. Used by `/age` and `/cure` to scope reviews.

```sh
# Install (Python 3.10+ required)
pip install code-review-graph   # or: pipx install code-review-graph

# Auto-detect and configure your harness
code-review-graph install

# Target a specific harness
code-review-graph install --platform claude-code
code-review-graph install --platform cursor
code-review-graph install --platform codex

# Build the graph for the current project (re-run after large changes)
code-review-graph build
```

## Installing CLI tools

The optional tools in the table below are referenced by workflow skills. None are required, but having them available unlocks better fallbacks and richer output.

### GitHub CLI (`gh`)

```sh
brew install gh           # macOS/Linux via Homebrew
winget install GitHub.cli # Windows
# or see https://cli.github.com for other methods
gh auth login
```

Minimum version for `gh skill`: **v2.90.0**.

```sh
gh --version
```

`gh skill` ships as a built-in subcommand in GitHub CLI v2.90.0+. If your installation predates that release, upgrade `gh` rather than installing an extension. Check [cli.github.com/manual/gh_skill](https://cli.github.com/manual/gh_skill) for the current status.

### ast-grep (`sg`)

Used by `/cook`, `/age`, and `/cure` for structural codemods when tilth is unavailable.

```sh
brew install ast-grep          # macOS/Linux
npm install -g @ast-grep/cli   # Node.js
cargo install ast-grep         # Rust/Cargo
scoop install ast-grep         # Windows (Scoop)
```

### ripgrep (`rg`)

Fast text search used as a fallback when tilth is unavailable.

```sh
brew install ripgrep           # macOS/Linux
winget install BurntSushi.ripgrep.MSVC  # Windows
cargo install ripgrep          # Rust/Cargo
```

### delta

Human-readable diffs used by `/age` and `/cure`.

```sh
brew install git-delta         # macOS/Linux
cargo install git-delta        # Rust/Cargo
winget install dandavison.delta # Windows
```

Add to `~/.gitconfig` to enable globally:

```ini
[core]
    pager = delta
[interactive]
    diffFilter = delta --color-only
```

### mergiraf

Structured merge-conflict resolution used by `/melt`.

```sh
cargo install mergiraf         # Rust/Cargo
brew install mergiraf          # macOS/Linux (if tap is available)
```

### `jq`

JSON inspection used by various skills for structured output.

```sh
brew install jq                # macOS/Linux
winget install jqlang.jq       # Windows
apt-get install jq             # Debian/Ubuntu
```

### `fd`

Fast file discovery used as a fallback when tilth is unavailable.

```sh
brew install fd                # macOS/Linux
cargo install fd-find          # Rust/Cargo
winget install sharkdp.fd      # Windows
apt-get install fd-find        # Debian/Ubuntu
```

### `just`

Project task runner used by `/cook` and `/press` to discover and run project commands.

```sh
brew install just              # macOS/Linux
cargo install just             # Rust/Cargo
winget install Casey.Just      # Windows
```
