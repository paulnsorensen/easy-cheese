# 🧀 easy-cheese 🧀

[![CI](https://img.shields.io/github/actions/workflow/status/paulnsorensen/easy-cheese/validate.yml?branch=main&label=CI&style=flat-square)](https://github.com/paulnsorensen/easy-cheese/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/github/license/paulnsorensen/easy-cheese?style=flat-square)](LICENSE)
[![Latest release](https://img.shields.io/github/v/release/paulnsorensen/easy-cheese?style=flat-square)](https://github.com/paulnsorensen/easy-cheese/releases/latest)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/paulnsorensen/easy-cheese/badge)](https://scorecard.dev/viewer/?uri=github.com/paulnsorensen/easy-cheese)
[![CodeQL](https://github.com/paulnsorensen/easy-cheese/actions/workflows/codeql.yml/badge.svg)](https://github.com/paulnsorensen/easy-cheese/actions/workflows/codeql.yml)
[![skills.sh](https://skills.sh/b/paulnsorensen/easy-cheese)](https://skills.sh/paulnsorensen/easy-cheese)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow?style=flat-square)](https://www.conventionalcommits.org)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-spec-blueviolet?style=flat-square)](https://agentskills.io/specification)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](https://github.com/paulnsorensen/easy-cheese/pulls)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy_Me_a_Coffee-FFDD00?style=flat-square&logo=buymeacoffee&logoColor=black)](https://www.buymeacoffee.com/paulnsorensen)

**Don't know what to do? Just `/cheese` it.**

> _"The cheese must flow."_

A portable, harness-agnostic Agent Skills toolkit — self-contained `SKILL.md` files any [Agent Skills](https://agentskills.io/specification)-compatible harness can load. No agents, no compiled bundles, no repo-wide MCP requirement. The vocabulary (mold, culture, cook, press, age, cure) reads as a workflow you can dip into anywhere.

## Contents

- [Why cheese?](#why-cheese-two-reasons)
- [Skill layout](#skill-layout)
- [Skills](#skills)
- [Scope](#scope)
- [Optional tools](#optional-tools)
- [Install](#install)
- [Validate](#validate)
- [Installing MCP servers](#installing-mcp-servers)
- [Installing CLI tools](#installing-cli-tools)
- [Credits](#credits)

## Why cheese? Two reasons

1. **From gaming slang**: a "cheese" win is cheap, easy, and disproportionately effective — exactly the design center (correctness, token efficiency, quality).
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

Content shared _across_ skills lives at top-level `shared/` (e.g. `shared/handoff-gate.md`), sibling to `skills/` rather than inside any one skill's `references/`. Skills reference it by relative path (`../../shared/<file>.md`). The top-level location keeps it out of skill auto-discovery and signals that it's a cross-cutting contract, not a private detail of any single skill.

## Skills

### Workflow skills

| Skill path | Command | Purpose |
| --- | --- | --- |
| `skills/cheese/SKILL.md` | `/cheese` | Unified entry point. Classifies any input (idea, spec path, PR, stack trace, file path), announces the routing decision as a short three-line block (Intent / Reason / Target), and dispatches the chosen target immediately with `--auto` propagated downstream. Add `--safe` to gate dispatch behind a confirmation prompt and surface non-auto alternatives. |
| `skills/briesearch/SKILL.md` | `/briesearch` | Research technical questions across docs, web, codebase, and GitHub examples with confidence-capped synthesis. |
| `skills/mold/SKILL.md` | `/mold` | Shape fuzzy ideas into grounded specs through dialogue, validate cycles, and a two-key handshake. |
| `skills/culture/SKILL.md` | `/culture` | The agent's internal-thinking skill — invoked silently by `/cheese` and other workflow skills to model a problem before dispatching. Surfaces to the user only when they explicitly opted out of writes ("no writes", "rubber-duck this"). Hard invariant: writes only the opt-in `.cheese/notes/<slug>.md` handoff at session end, and only when the user asks for notes. |
| `skills/pasteurize/SKILL.md` | `/pasteurize` | Diagnose hard bugs, flaky failures, and performance regressions with a feedback-loop-first investigation, then hand off into `/cook → /press → /age → /cure`. |
| `skills/cook/SKILL.md` | `/cook` | Implement clear specs via cut → cook → taste-test with scoped edits and tests. |
| `skills/press/SKILL.md` | `/press` | Harden cooked changes with coverage, assertion, and boundary checks. |
| `skills/age/SKILL.md` | `/age` | Review diffs across nine staff-engineer dimensions and produce a severity-grouped findings report. |
| `skills/affinage/SKILL.md` | `/affinage` | Triage external PR claims — review comments and CI failures — through the `/age` lens, hand the chosen fixes to `/cure`, then post replies back on GitHub. |
| `skills/cure/SKILL.md` | `/cure` | Fix user-selected findings, validate, and prepare the branch for shipping. |
| `skills/hard-cheese/SKILL.md` | `/hard-cheese` (or `--hard` flag) | Metacognitive vibecheck gate before review — asks the author to explain the diff's causal logic, grades the explanation against the SOLO Taxonomy. Standalone or via `--hard` propagation through the pipeline. |
| `skills/ultracook/SKILL.md` | `/ultracook` | Autonomous fresh-context pipeline (`cook → press → age → cure → age → cure → age`, all `--auto`). Each phase runs inside its own full-peer sub-agent so review stays adversarial and parent context never bloats. For high-blast-radius specs. |
| `skills/cheese-factory/SKILL.md` | `/cheese-factory` | Large-feature orchestrator. Decomposes an approved spec into seed + parallel curds + wiring, fans out per-curd `/cook → /press → /age → /cure`, merges, runs a fresh-context post-merge review pass, and ends in 1–N reviewable PRs (single, orthogonal flat, stacked linear, or diamond-stacked). Portable, harness-agnostic sibling of `/fromagerie`. |
| `skills/melt/SKILL.md` | `/melt` | Resolve merge / rebase / cherry-pick conflicts via the structural cascade (mergiraf → rerere → kdiff3) with batch, pick-side, and lockfile helpers. |
| `skills/wheypoint/SKILL.md` | `/wheypoint` | Mark a checkpoint: compact a mid-task conversation into a durable handoff document at `.cheese/notes/<slug>.md` (resumable slug + state-mapped suggested-skills + redacted secrets) so a fresh agent can resume via `/cheese --continue <slug>`. |

### Tool skills

The workflow skills can delegate code search, reading, and editing to these MCP-backed skills when tilth is available:

| Skill path | Command | Purpose |
| --- | --- | --- |
| `skills/cheez-search/SKILL.md` | `/cheez-search` | AST-aware code/text/regex/caller search via tilth MCP. Replaces grep / rg / find. |
| `skills/cheez-read/SKILL.md` | `/cheez-read` | Smart file/directory reading with hash anchors via tilth MCP. Replaces cat / head / tail / ls. |
| `skills/cheez-write/SKILL.md` | `/cheez-write` | Hash-anchored, surgical edits via tilth MCP. Never rewrites whole files. |

The `cheez-*` skills require tilth MCP and hard-fail when it is unavailable rather than fall back to host tools. Workflow skills remain portable by falling back directly to host-native tools when they are not using `cheez-*`.

#### cheez-* router protocol

The three `cheez-*` skills are designed to chain. The standard sequence:

1. **`/cheez-search`** — locate the symbol, caller, content match, or file. AST-aware; replaces grep/rg/find.
2. **`/cheez-read`** — read the target file or section to capture hash anchors. Smart-outlines large files; replaces cat/head/tail/ls.
3. **`/cheez-write`** — apply hash-anchored edits with the anchors from step 2. Surgical; rejects on hash mismatch.

Workflow skills (`/cook`, `/age`, `/cure`) call into this chain when they need code intelligence. A skill should never search-then-edit without reading in between — the read is what produces the anchors that make the edit safe.

##### Tool redirection map

If you'd reach for one of these on a code task, route through `cheez-*` instead:

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

Outside code work (e.g. `find -mtime`, `ls /tmp`, log inspection with `tail -f`, JSON munging with `jq`) the host tools are still the right call. The redirection rule is: **anything that touches source code goes through `cheez-*`**.

#### Installing tilth MCP

See [Installing MCP servers](#installing-mcp-servers) below — expand the tilth section for full instructions.

If those tools don't show up after install, the `cheez-*` skills will hard-fail with "tilth MCP server is not loaded" instead of silently falling back to host tools.

### Suggested flow

```text
/cheese  ──►  classify intent  ──►  dispatch immediately (autonomous by default)
   ├─ need info / external evidence  ──►  /briesearch
   ├─ no-writes discussion only      ──►  /culture                  (user explicitly opted out of writes)
   ├─ fuzzy / multi-module idea       ──►  /mold        ──►  /cook --auto      ──►  /press  ──►  /age  ──►  /cure
   ├─ high-blast-radius spec          ──►  /mold        ──►  /ultracook        (fresh-context: cook → press → age → cure → age → cure → age)
   ├─ clear, scoped ask               ──►  /cook --auto                                                ──►  /press  ──►  /age  ──►  /cure
   ├─ debugging task                  ──►  /pasteurize --auto ──►  /cook --auto                        ──►  /press  ──►  /age  ──►  /cure
   ├─ PR comments / CI failures       ──►  /affinage    ──►  /cure
   ├─ running low on context          ──►  /wheypoint  ──►  /cheese --continue <slug>   (fresh session)
   ├─ resume in fresh context         ──►  /cheese --continue <slug>
   └─ review only                     ──►  /age         ──►  /cure
```

`/cheese` is the front door. It inspects whatever you drop in (idea, spec path,
PR ref, stack trace, file path), announces its routing decision as a short
three-line block (Intent / Reason / Target), and dispatches the chosen skill in
the same turn — `--auto` propagates
downstream so the chain runs all the way through. Use `--safe` when you want
the chance to redirect before anything runs: it puts the confirmation prompt
back in front of dispatch and surfaces non-auto variants as alternatives. Skip
`/cheese` entirely when you already know the destination — a hard bug can go
straight to `/pasteurize`, a known-scope fix can go to `/cook`, and an
explicit no-writes design discussion goes to `/culture`. `/melt` cuts in
whenever a merge step blocks `/cook` or `/cure`. Append `--hard` to any
pipeline step to insert `/hard-cheese` as a metacognitive vibecheck gate
before review.

## Scope

Easy-cheese is intentionally a small surface. What that means in practice:

- **Skills only.** No agents, commands, eta templates, or compiled harness bundles. Each capability is a single `SKILL.md`.
- **No repo-wide MCP requirement.** Workflow skills suggest tools (tilth, Context7, Tavily, code-review-graph) but have host-native fallbacks. The `cheez-*` tool skills are the exception: they require tilth MCP by design.
- **One orchestrator skill, narrowly scoped.** `/ultracook` is the only orchestrator — it spawns full-peer sub-agents for the fixed `cook → press → age → cure → age → cure → age` chain on high-blast-radius specs. There is no large-feature decomposition, no PR-rescue convoy, no whole-repo NIH audit. Every other skill remains a single, scoped step a human can drive.
- **No automatic re-age loop in `/cure`.** The skill describes the protocol; the human runs the next `/age` when ready.

## Optional tools

Workflow skills name preferred tools when they help, with fallbacks for portability. Tool skills can be stricter when their purpose is to enforce a specific tool protocol.

| Tool | Helps with | Fallback |
| --- | --- | --- |
| tilth (MCP) | AST-aware read/search/edit and dependency context | Required for cheez-\*; workflow skills can bypass cheez-\* and use host read/edit, `ripgrep`, patches |
| `sg` (ast-grep) | Structural pattern matching and codemods (`sg --rewrite`) with metavariables | `ripgrep`, `find`, targeted reads; `tilth_edit` for non-structural edits |
| Context7 (MCP) | Library and API documentation | repo docs, package docs, vendor pages, web search |
| Tavily (MCP) | Current web/vendor research | host web search or user-supplied sources |
| code-review-graph (MCP) | Review impact radius, architecture framing, and embeddings-backed semantic / cross-repo search | import searches, caller searches, tests |
| LSP / [Serena](https://github.com/oraios/serena) (MCP) | Type-aware xrefs (`find_referencing_symbols`, `find_implementations`), symbol-bounded edits (`rename_symbol`, `replace_symbol_body`, `safe_delete_symbol`), and LSP diagnostics — concrete tools for the abstract "if your harness has an LSP" sections in `cheez-*` skills | `sg`, `tilth_search`, targeted reads via tilth |
| `ripgrep` | Fast text search | `grep`, `find`, editor search |
| `gh` | GitHub issues, PRs, checks, examples | local git commands or user-provided links/logs |
| `delta` | Readable diffs | plain `git diff` |
| `mergiraf` | Structured merge conflict resolution | manual conflict resolution plus tests |
| `jq` | JSON inspection for reports or tool output | manual inspection |
| `fd` | Fast file discovery | `find` |
| `just` | Project task discovery | package scripts or documented commands |

When a preferred tool is unavailable, workflow skills say so once, fall back, and lower confidence only if evidence quality suffers. The `cheez-*` skills stop instead because tilth is their compatibility requirement.

## Install

### skills.sh (recommended)

Install with the [skills.sh](https://skills.sh) installer:

```sh
npx skills@latest add paulnsorensen/easy-cheese
```

The installer reads this repo's published skill manifest, lets you pick the
skills you want, and installs them into the coding agents you select.

After install, start with `/cheese` if you're not sure which wheel to cut into
first, or jump straight to a specific skill like `/cook`, `/age`, or
`/pasteurize`. There is no required follow-up setup skill.

### gh skill (GitHub CLI alternative)

Requires [GitHub CLI](https://cli.github.com) v2.90.0 or later with the `gh skill` command.

Install all skills interactively:

```sh
gh skill install paulnsorensen/easy-cheese
```

Install every current skill in one shot:

```sh
for s in age affinage briesearch cheese cheese-factory cheez-read cheez-search cheez-write cook culture cure hard-cheese melt mold pasteurize press ultracook; do
  gh skill install paulnsorensen/easy-cheese "$s"
done
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
# User-wide (recommended for personal toolkits)
gh skill install paulnsorensen/easy-cheese --agent claude-code --scope user

# Committed into the current project repo (default scope)
gh skill install paulnsorensen/easy-cheese --agent claude-code --scope project
```

Supported `--agent` values include `github-copilot`, `claude-code`, `cursor`, `codex`, `gemini-cli`, and others. Omit `--agent` to use the harness auto-detected from your environment.

Preview a skill's content before committing to an install:

```sh
gh skill preview paulnsorensen/easy-cheese cook
```

Keep installed skills up to date:

```sh
gh skill update --all
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
pip install skills-ref   # ships the `agentskills` CLI
agentskills validate ./skills/age
```

Each `SKILL.md` must have YAML frontmatter with at least `name` and `description`, and `name` must match the parent directory name.

## Installing MCP servers

The `cheez-*` tool skills and several workflow skills benefit from MCP servers. Install the ones you need.

<details>
<summary><strong>tilth</strong> (required for `cheez-*` skills) — AST-aware code search, smart reading, hash-anchored edits</summary>

[tilth](https://github.com/jahala/tilth) provides AST-aware code search, smart file reading, and hash-anchored edits. Required by `/cheez-search`, `/cheez-read`, and `/cheez-write`.

```sh
# Install tilth CLI — pick one (no Homebrew formula upstream)
cargo install tilth        # via Cargo (Rust) — preferred, native binary
npm install -g tilth       # via npm (Node 18+) — no Rust toolchain needed
# or run via npx — no global install needed (Node.js v18+):
#   npx -y tilth install claude-code --edit

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

</details>

<details>
<summary><strong>Context7</strong> — library documentation for <code>/briesearch</code> and <code>/cook</code></summary>

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

</details>

<details>
<summary><strong>Tavily</strong> — web search for <code>/briesearch</code></summary>

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

</details>

<details>
<summary><strong>code-review-graph</strong> — impact radius, architecture framing, semantic search for <code>/age</code>, <code>/press</code>, <code>/cure</code></summary>

[code-review-graph](https://github.com/tirth8205/code-review-graph) builds a persistent call graph of your codebase with Tree-sitter, Louvain communities, betweenness-centrality, and optional vector embeddings. Used by `/age`, `/press`, and `/cure` for risk-scored impact (`get_impact_radius_tool`, `detect_changes_tool`), curated review context (`get_review_context_tool`, `get_minimal_context_tool`), affected flows (`get_affected_flows_tool`), architecture framing (`get_architecture_overview_tool`, `get_hub_nodes_tool`, `get_bridge_nodes_tool`), and cross-repo / semantic search (`cross_repo_search_tool`, `semantic_search_nodes_tool`). Tilth handles AST search, callers, and hash-anchored edits; code-review-graph covers the graph-algorithmic and cross-repo dimensions tilth does not.

```sh
# Install with the local sentence-transformers embeddings extra (Python 3.10+ required)
pip install 'code-review-graph[embeddings]'   # or: pipx install 'code-review-graph[embeddings]'

# Auto-detect and configure your harness
code-review-graph install

# Target a specific harness
code-review-graph install --platform claude-code
code-review-graph install --platform cursor
code-review-graph install --platform codex

# Build the graph for the current project (re-run after large changes)
code-review-graph build

# Compute embeddings for semantic_search_nodes_tool (one-time, then incremental)
code-review-graph embed
```

The `[embeddings]` extra pulls in `sentence-transformers` so `semantic_search_nodes_tool` works out of the box with the default `all-MiniLM-L6-v2` model. Override with `CRG_EMBEDDING_MODEL=<model-id>`. Other embedding providers (Google Gemini, MiniMax, OpenAI-compatible endpoints) are also supported — see the upstream README for `[google-embeddings]` and the `CRG_OPENAI_*` env vars.

</details>

## Installing CLI tools

The optional tools listed under [Optional tools](#optional-tools) are referenced by workflow skills. None are required, but having them available unlocks better fallbacks and richer output.

### macOS bootstrap script (optional)

Use
[`scripts/install.sh`](https://github.com/paulnsorensen/easy-cheese/blob/main/scripts/install.sh)
when you want the surrounding macOS toolchain and MCP servers set up for you.
The recommended way to install the skills themselves is still the `skills.sh`
flow above; this script is the fast lane for the wider ecosystem.

It does the following in one shot:

1. Installs every CLI tool listed below — Homebrew for the eight brew-core formulas, plus `cargo install tilth` (or `npm install -g tilth` if Rust isn't available) for tilth, which has no Homebrew formula upstream.
2. Auto-detects installed Claude Code, Cursor, and Codex CLIs, then installs every easy-cheese skill into each detected harness at user scope as a convenience bootstrap.
3. Registers the `tilth` and `context7` MCP servers with those harnesses where supported.

Currently macOS only — it relies on Homebrew. Requires `gh` to be authenticated (`gh auth login`) before running.

Pipe straight from GitHub:

```sh
curl -fsSL https://raw.githubusercontent.com/paulnsorensen/easy-cheese/main/scripts/install.sh | bash
```

Or grab the script first if you'd like to read it:

```sh
curl -fsSL -o /tmp/easy-cheese-install.sh https://raw.githubusercontent.com/paulnsorensen/easy-cheese/main/scripts/install.sh
bash /tmp/easy-cheese-install.sh --help
bash /tmp/easy-cheese-install.sh --dry-run
```

Common flags:

```sh
# Install only ripgrep + jq, skip MCP registration
curl -fsSL https://raw.githubusercontent.com/paulnsorensen/easy-cheese/main/scripts/install.sh \
  | bash -s -- --tools ripgrep,jq --skip-mcp

# Register MCP servers only (assumes CLI tools and skills are already installed)
curl -fsSL https://raw.githubusercontent.com/paulnsorensen/easy-cheese/main/scripts/install.sh \
  | bash -s -- --skip-tools --mcp tilth,context7,tavily

# Pick a specific harness for skill + MCP registration
curl -fsSL https://raw.githubusercontent.com/paulnsorensen/easy-cheese/main/scripts/install.sh \
  | bash -s -- --harness cursor

# Or target a comma-separated harness list explicitly
curl -fsSL https://raw.githubusercontent.com/paulnsorensen/easy-cheese/main/scripts/install.sh \
  | bash -s -- --harness claude-code,cursor,codex
```

The script is idempotent — it skips any tool already on `PATH` — and accepts `--dry-run` so you can preview what it would do before letting it run. If no supported harness CLI is detected, it falls back to the historical `claude-code` target; pass `--harness` to override detection.

> **Heads-up:** `curl | bash` runs whatever the URL serves at the moment of the request. If you want to audit before running, use the two-step form above.

If you'd rather install tools individually, the per-tool sections below cover macOS, Windows, and Linux.

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

## Credits

The shared voice kernel at [`skills/age/references/voice.md`](skills/age/references/voice.md) — output discipline, reasoning posture, the `certain | speculating | don't know` confidence vocabulary, and the depth-vs-question split — adapts a [Claude Opus 4.7 system-prompt experiment by Reebz](https://gist.github.com/Reebz/b81ad99409d5b5de3045bebde71d4471), narrowed to the parts that earn their keep in a portable skills toolkit. Cross-referenced from `briesearch`, `culture`, `mold`, `cook`, and `cure`.

The `/pasteurize` skill — the six-phase diagnosis loop (feedback loop → reproduce → hypothesise → instrument → fix + regression test → cleanup) and the "build a feedback loop first" insight — adapts [Matt Pocock's `diagnose` skill](https://github.com/mattpocock/skills/blob/main/skills/engineering/diagnose/SKILL.md). Easy-cheese-specific adaptations (`cheez-*` tooling, handoff slug schema, `--auto` chain, `/cook` handoff for Phase 5) are layered on top.

The `/wheypoint` skill — compacting a conversation into a handoff document (with a suggested-skills section, no-duplication of existing artifacts, and secret redaction) — adapts [Matt Pocock's `handoff` skill](https://github.com/mattpocock/skills/blob/main/skills/productivity/handoff/SKILL.md). Easy-cheese-specific adaptations: the handoff lands as a durable, resumable artifact at `.cheese/notes/<slug>.md` (rather than the OS temp directory) carrying the standard handoff slug, the suggested-skills section is a state-to-skill mapping over the cheese pipeline expressed as the slug's `next:` field plus named skills, and resumption runs through `/cheese --continue <slug>`.
