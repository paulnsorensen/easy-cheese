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

Content shared _across_ skills lives in the `cheese` skill's `references/` directory (e.g. `skills/cheese/references/handoff-gate.md`). Full installs include `cheese`; when installing one workflow skill, install `cheese` alongside it. Skills reference shared material by sibling-relative path (`../cheese/references/<file>.md` from a `SKILL.md`, `../../cheese/references/<file>.md` from a `references/*.md`) so links resolve identically in the repo tree and any installed skills directory.

## Skills

### Workflow skills

| Skill path | Command | Purpose |
| --- | --- | --- |
| `skills/cheese/SKILL.md` | `/cheese` | Unified entry point. Classifies any input (idea, spec path, PR, stack trace, file path), announces the routing decision as a short three-line block (Intent / Reason / Target), and dispatches the chosen target immediately with `--auto` propagated downstream. Add `--safe` to gate dispatch behind a confirmation prompt and surface non-auto alternatives. |
| `skills/briesearch/SKILL.md` | `/briesearch` | Research technical questions across docs, web, codebase, and GitHub examples with confidence-capped synthesis. |
| `skills/mold/SKILL.md` | `/mold` | Shape fuzzy ideas into grounded specs through dialogue, validate cycles, and a two-key handshake. |
| `skills/culture/SKILL.md` | `/culture` | The agent's internal-thinking skill — invoked silently by `/cheese` and other workflow skills to model a problem before dispatching. Surfaces to the user only when they explicitly opted out of writes ("no writes", "rubber-duck this"). Hard invariant: writes only the opt-in `.cheese/notes/<slug>.md` handoff at session end, and only when the user asks for notes. |
| `skills/pasteurize/SKILL.md` | `/pasteurize` | Diagnose hard bugs, flaky failures, and performance regressions with a feedback-loop-first investigation, then hand off into `/cook → /press → /age → /cure`. |
| `skills/cook/SKILL.md` | `/cook` | Single implementation orchestrator: runs a focused spec through one coder or fans an approved curd block through fresh-context phase agents. |
| `skills/press/SKILL.md` | `/press` | Harden cooked changes with coverage, assertion, and boundary checks. |
| `skills/age/SKILL.md` | `/age` | Review diffs across ten staff-engineer dimensions and produce a severity-grouped findings report. |
| `skills/affinage/SKILL.md` | `/affinage` | Triage external PR claims — review comments and CI failures — through the `/age` lens, hand the chosen fixes to `/cure`, then post replies back on GitHub. |
| `skills/cure/SKILL.md` | `/cure` | Fix user-selected findings, validate, and prepare the branch for shipping. |
| `skills/plate/SKILL.md` | `/plate` | Final writing, validation, commit, and ordinary-or-stacked PR publication gate. Explicit topology choices win; obvious cohesive work opens as one PR, while stack recommendations and ambiguous shapes ask before mutation. |
| `skills/hard-cheese/SKILL.md` | `/hard-cheese` (or `--hard` flag) | Metacognitive vibecheck gate before review — asks the author to explain the diff's causal logic, grades the explanation against the SOLO Taxonomy. Standalone or via `--hard` propagation through the pipeline. |
| `skills/ultracook/SKILL.md` | `/ultracook` | Compatibility redirect to `/cook`; its retained scripts, references, and manifest paths remain fan-path internals consumed by `/cook`. |
| `skills/melt/SKILL.md` | `/melt` | Resolve merge / rebase / cherry-pick conflicts via the structural cascade (mergiraf → rerere → kdiff3) with batch, pick-side, and lockfile helpers. |
| `skills/wheypoint/SKILL.md` | `/wheypoint` | Mark a checkpoint: compact a mid-task conversation into a durable handoff document at `.cheese/notes/<slug>.md` (resumable slug + state-mapped suggested-skills + redacted secrets) so a fresh agent can resume via `/cheese --continue <slug>`. |

### Source-code routing

Workflow skills call source-code backends directly rather than dispatching wrapper skills. The shared [`code-intelligence-routing.md`](skills/cheese/references/code-intelligence-routing.md) contract defines capability selection and the mandatory search → fresh bounded read → stale-safe write sequence.

Dispatching skills resolve agent type, power, permissions, isolation, and fallback through the shared [`agent-resolution.md`](skills/cheese/references/agent-resolution.md) contract.

#### Installing tilth MCP

See [Installing MCP servers](#installing-mcp-servers) below — expand the tilth section for the preferred broad source-code backend. If tilth is unavailable, use equivalent native AST/LSP/anchored-edit tooling when the harness provides it; otherwise name the weaker fallback instead of pretending blind shell tools have the same safety.

### Suggested flow

```text
/cheese  ──►  classify intent  ──►  dispatch immediately (autonomous by default)
   ├─ need info / external evidence  ──►  /briesearch
   ├─ no-writes discussion only      ──►  /culture                  (user explicitly opted out of writes)
   ├─ fuzzy / multi-module idea       ──►  /mold        ──►  /cook --auto      ──►  /press  ──►  /age  ──►  /cure
   ├─ high-blast-radius spec          ──►  /mold        ──►  /cook --auto      (fresh-context fan pathway)
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
- **No repo-wide MCP requirement.** Workflow skills suggest tools (tilth, Context7, Tavily) but have host-native fallbacks. Source-code work follows the shared routing contract: prefer tilth when present, use equivalent native AST/LSP/anchored-edit backends when available, and report any precision loss from bounded fallbacks.
- **One orchestrator skill, narrowly scoped.** `/cook` is the single implementation orchestrator: focused specs use its single-coder path, while approved file-disjoint curds use its fresh-context fan pathway. `/ultracook` is only a compatibility redirect to `/cook`. Harvest and `/plate` remain parent-owned; parallel curds use sequential same-worktree phase spawns and a terminal reviewer pass before publication.
- **No automatic re-age loop in `/cure`.** The skill describes the protocol; the human runs the next `/age` when ready.

## Optional tools

Workflow skills name preferred tools when they help, with bounded fallbacks for portability.

| Tool | Helps with | Fallback |
| --- | --- | --- |
| tilth (MCP) | AST-aware read/search/edit and dependency context | Native AST/LSP/anchored-edit tools per the shared routing contract |
| `sg` (ast-grep) | Structural pattern matching and codemods (`sg --rewrite`) with metavariables | LSP or tilth for symbol/caller questions; anchored edits for non-structural block changes |
| Context7 (MCP) | Library and API documentation | repo docs, package docs, vendor pages, web search |
| Tavily (MCP) | Current web/vendor research | host web search or user-supplied sources |
| LSP / [Serena](https://github.com/oraios/serena) (MCP) | Type-aware xrefs (`find_referencing_symbols`, `find_implementations`), symbol-bounded edits (`rename_symbol`, `replace_symbol_body`, `safe_delete_symbol`), and LSP diagnostics | `sg`, `tilth_search`, targeted reads via tilth |
| hallouminate (MCP) | Per-repo wiki for cross-session design rationale, ADR grounding, and `/mold` evidence | Skip wiki grounding; proceed with diff + code evidence only; cap at `speculating` when design rationale is central |
| milknado (MCP) | Mikado task-graph backend for `/cook`'s fan-path curd prerequisite tracking | In-report curd decomposition in manifest YAML; no external task-graph backend needed |
| `ripgrep` | Fast text search | `grep`, `find`, editor search |
| `gh` | GitHub issues, PRs, checks, examples | local git commands or user-provided links/logs |
| `delta` | Readable diffs | plain `git diff` |
| `mergiraf` | Structured merge conflict resolution | manual conflict resolution plus tests |
| `jq` | JSON inspection for reports or tool output | manual inspection |
| `fd` | Fast file discovery | `find` |
| `just` | Project task discovery | package scripts or documented commands |

When a preferred tool is unavailable, workflow skills say so once, use the strongest bounded fallback, and lower confidence only if evidence quality suffers.

## Install

### skills.sh (recommended)

Install every skill with the [skills.sh](https://skills.sh) installer. The
skills form one pipeline (`/cheese → /mold → /cook → /press → /age → /cure`),
so install them together rather than cherry-picking:

```sh
npx skills@latest add paulnsorensen/easy-cheese --all --global
```

`--all` is shorthand for `--skill "*" --agent "*" -y`: every published skill,
into every detected agent, no prompts. `--global` installs them user-wide, so
they are available across every repo.

To scope the install to just the current repo instead (recorded under
`.agents/skills/`), drop `--global` and run it from that repo:

```sh
npx skills@latest add paulnsorensen/easy-cheese --all
```

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
for s in age affinage briesearch cheese cook culture cure hard-cheese melt mold pasteurize press ultracook wheypoint; do
  gh skill install paulnsorensen/easy-cheese "$s"
done
```

Install one workflow skill with its shared contracts:

```sh
gh skill install paulnsorensen/easy-cheese cheese
gh skill install paulnsorensen/easy-cheese cook
```

Pin both skills to the same release tag or commit SHA for reproducibility:

```sh
gh skill install paulnsorensen/easy-cheese cheese@v0.10.1
gh skill install paulnsorensen/easy-cheese cook@v0.10.1
gh skill install paulnsorensen/easy-cheese cheese@abc123def
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

Several workflow skills benefit from MCP servers. Install the ones you need.

<details>
<summary><strong>tilth</strong> — AST-aware code search, smart reading, tag-anchored edits</summary>

[tilth](https://www.npmjs.com/package/@paulnsorensen/tilth-nightly) provides the preferred broad source search/read/edit backend. Equivalent native AST/LSP/anchored-edit backends satisfy the shared source-code routing contract when Tilth is unavailable.

```sh
# Install tilth CLI via npm (Node.js v18+) — no Homebrew formula upstream
npm install -g @paulnsorensen/tilth-nightly@latest
# or run via npx — no global install needed:
#   npx -y @paulnsorensen/tilth-nightly@latest install claude-code --edit

# Register as an MCP server — include --edit for tag-anchored writes
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
- `mcp__tilth__tilth_list`
- `mcp__tilth__tilth_deps`
- `mcp__tilth__tilth_write` (only with `--edit`)

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

## Installing CLI tools

The optional tools listed under [Optional tools](#optional-tools) are referenced by workflow skills. None are required, but having them available unlocks better fallbacks and richer output.

### macOS bootstrap script (optional)

Use
[`scripts/install.sh`](https://github.com/paulnsorensen/easy-cheese/blob/main/scripts/install.sh)
when you want the surrounding macOS toolchain and MCP servers set up for you.
The recommended way to install the skills themselves is still the `skills.sh`
flow above; this script is the fast lane for the wider ecosystem.

It does the following in one shot:

1. Installs every CLI tool listed below — Homebrew for the eight brew-core formulas, plus `npm install -g @paulnsorensen/tilth-nightly@latest` for tilth, which has no Homebrew formula upstream.
2. Auto-detects installed Claude Code, Cursor, and Codex CLIs, then installs every easy-cheese skill into each detected harness at user scope as a convenience bootstrap.
3. Registers the `tilth`, `context7`, and `hallouminate` MCP servers with those harnesses where supported. hallouminate is delivered as a plugin: on `claude-code` and `codex` the installer adds the `paulnsorensen/hallouminate` plugin marketplace and installs the plugin (which ships its own MCP server and bootstraps the binary); on other harnesses it warns and you register the MCP manually. Other servers (`tavily`, `milknado`) are also selectable with `--mcp`.

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

The `/plate` skill's semantics-preserving/semantics-altering review-unit policy adapts Jeff Sarnat's [Structuring Changes With The Code Reviewer in Mind](https://jeff.sarn.at/blog/structuring-changes-with-the-code-reviewer-in-mind). `/plate`'s PR-topology, commit-shaping, and verification-body rules are project-specific extensions of that principle.

The shared voice kernel at [`skills/age/references/voice.md`](skills/age/references/voice.md) — output discipline, reasoning posture, the `certain | speculating | don't know` confidence vocabulary, and the depth-vs-question split — adapts a [Claude Opus 4.7 system-prompt experiment by Reebz](https://gist.github.com/Reebz/b81ad99409d5b5de3045bebde71d4471), narrowed to the parts that earn their keep in a portable skills toolkit. Cross-referenced from `briesearch`, `culture`, `mold`, `cook`, and `cure`.

The `/pasteurize` skill — the six-phase diagnosis loop (feedback loop → reproduce → hypothesise → instrument → fix + regression test → cleanup) and the "build a feedback loop first" insight — adapts [Matt Pocock's `diagnose` skill](https://github.com/mattpocock/skills/blob/main/skills/engineering/diagnose/SKILL.md). Easy-cheese-specific adaptations (shared source-code routing, handoff slug schema, `--auto` chain, `/cook` handoff for Phase 5) are layered on top.

The `/wheypoint` skill — compacting a conversation into a handoff document (with a suggested-skills section, no-duplication of existing artifacts, and secret redaction) — adapts [Matt Pocock's `handoff` skill](https://github.com/mattpocock/skills/blob/main/skills/productivity/handoff/SKILL.md). Easy-cheese-specific adaptations: the handoff lands as a durable, resumable artifact at `.cheese/notes/<slug>.md` (rather than the OS temp directory) carrying the standard handoff slug, the suggested-skills section is a state-to-skill mapping over the cheese pipeline expressed as the slug's `next:` field plus named skills, and resumption runs through `/cheese --continue <slug>`.

The Superpowers [`brainstorming`](https://github.com/ejfox/superpowers-mcp) skill — adapted into `/mold`'s design dialogue. Easy-cheese-specific adaptations: the agent-introduced-scope grep gate, shape-check blast-radius numbers, the two-key handshake (curdle gating on the user verb plus the agent's coherence self-check), and ADRs captured as a durable curdle by-product are ahead of the borrowed brainstorming flow.

The [`grill-with-docs`](https://github.com/mattpocock/skills/blob/main/skills/engineering/grill-with-docs/SKILL.md) skill (Pocock) — adapted into `/mold`'s Grill phase with grounded, cited claims: every critical claim is verified from local code or `/briesearch` before seams are locked.

The `cumulative-domain-model` feature — the cumulative ubiquitous-language discipline that grows a durable `domain-model.md` domain model across sessions — adapts [Matt Pocock's `domain-modeling` skill](https://github.com/mattpocock/skills/blob/main/skills/engineering/domain-modeling/SKILL.md). Easy-cheese-specific adaptations layer the cheese pipeline's grounding and artifact conventions on top.

The `/age` rubric's shallow-abstraction and exported-special-case rows — pass-through methods and variables, adjacent layers restating one abstraction, and error/default/config decisions a producer exports to every caller — adapt John Ousterhout's [_A Philosophy of Software Design_](https://web.stanford.edu/~ouster/cgi-bin/aposd.php), read through his [Stanford CS190 lecture notes on modular design](https://web.stanford.edu/~ouster/cgi-bin/cs190-winter18/lecture.php?topic=modularDesign) and the [APOSD vs Clean Code discussion](https://github.com/johnousterhout/aposd-vs-clean-code). `/mold`'s option-scoring line uses his stated design test — whether an idea reduces the information a developer must know, or makes that information more obvious. Easy-cheese-specific adaptations: the principles ship as computed-severity rubric rows with detection signals rather than prose advice, and the complexity dimension keeps its numeric budget as a mechanically-checkable smell trigger while adding the counterweight rows implied by his critique of arbitrary size limits and his "only decompose if it can be done cleanly" test.
