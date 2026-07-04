# Harness-native overlap

Where easy-cheese suggests or nudges a sub-agent, tool, skill, or MCP, and how
each nudge maps onto what the common harnesses provide natively. The durable
takeaway: **the one capability no common harness ships natively except oh-my-pi
(`omp`) is AST/structural search and first-class LSP-as-a-tool — which is
exactly what tilth / `cheez-*` fills.** Native sub-agents, the Agent Skills
spec, and MCP are now universal, so easy-cheese's portability bet holds and its
optional-MCP nudges are redundant only where the host also covers them natively.

Extends `tooling.md` ("tilth / cheez-* hard-fail vs optional MCP") with the
cross-harness grounding behind it. Companion analysis to
`skill-parity-analysis.md`.

## Two findings

- **tilth is redundant only on omp.** No common harness except omp ships a
  native AST/structural tool or LSP-as-a-tool (see Table 2). So `cheez-*`/tilth
  is the gap-filler that gives the workflow skills AST-awareness on every
  harness that isn't omp. The "pure redundancy" read of tilth holds on omp and
  only omp.
- **A shipped claim is stale.** easy-cheese states "Codex has no Agent
  primitive" (`skills/briesearch/SKILL.md:43`,
  `skills/cheese-factory/references/spawn-primitive-reference.md:63`). Codex now
  ships subagents (`default`/`worker`/`explorer`, parallel via
  `agents.max_threads`, custom TOML agents). Fix when next touching those files.

## Nudge surface — do we / should we (omp) / overlap

"Do we" = does easy-cheese currently nudge it. "Should (omp)" = worth keeping
when the host is omp, whose natives are the most complete.

### Sub-agents

| Nudge | Do we? | Should (omp)? | omp native overlap |
|---|---|---|---|
| Named phase-agents `reviewer`/`explorer`/`researcher`, read-only, never `general-purpose` (`skills/age/SKILL.md:98`, `cook/references/tdd-loop.md:39`, `cure/SKILL.md:37`, `briesearch/SKILL.md:43`) | Yes | Yes | omp has native `reviewer`/`explore`/`librarian`/`oracle`; the "named agent → `Explore` fallback" chain resolves natively |
| `Explore` read-only built-in fallback (`age/SKILL.md:98`, `affinage/SKILL.md:92`) | Yes | Yes | omp `explore` agent |
| `general-purpose` full-peer spawns (`cheese-factory`, `ultracook/SKILL.md:72`) | Yes | Yes | omp `task` agent |
| Parallel fan-out, one sub-agent per unit (`age/references/sub-agent-gate.md:29`) | Yes | Yes | omp `task` batch + `job` + `irc` |
| Inline-degrade when running as a sub-agent (`age/SKILL.md:276`) | Yes | Yes | omp caps nesting too; guard is correct |

All sub-agent nudges are sound and already harness-agnostic.

### Tools

| Nudge | Do we? | Should (omp)? | omp native overlap |
|---|---|---|---|
| Host read/grep/edit/write portable fallback (`README.md:87,161`) | Yes | Yes | direct |
| `sg` (ast-grep) structural / codemods (`README.md:107,172`) | Yes | Redundant | native `ast_grep` / `ast_edit` |
| LSP / Serena xrefs + symbol edits (`README.md:175`) | Yes | Redundant | native `lsp` |
| `ripgrep` / `find` / `fd` (`README.md:178,183`) | Yes | Partly redundant | `grep` / `glob` |
| `gh` for PR/issue/CI (`README.md:179`) | Yes | Keep | no native GitHub tool |
| `delta` / `mergiraf` / `jq` / `just` (`README.md:180-184`) | Yes | Keep | external CLIs; no native equivalent |

### Skills (cross-skill nudges)

| Nudge | Do we? | Should (omp)? | omp native overlap |
|---|---|---|---|
| Workflow chain handoffs culture → mold → cook → press → age → cure (`README.md:126-154`) | Yes | Yes — the product | none; no equivalent judgment vocabulary |
| `cheez-*` router protocol search → read → write (`README.md:89-118`) | Yes | Skip on omp (see MCP row) | natives do the same job |
| `next:` slug dispatch (`skills/cheese/SKILL.md:80-89`) | Yes | Yes | harness-agnostic |
| `--auto` / `--hard` flag propagation (`cheese/SKILL.md:61`) | Yes | Yes | pure skill logic |

The skill-to-skill nudges are the product — keep all. `cheez-*` is the one
"skill" nudge that is really a tool nudge.

### MCPs

| Nudge | Do we? | Should (omp)? | omp native overlap |
|---|---|---|---|
| **tilth** (`cheez-*` hard-dep) | Yes | Skip on omp; keep elsewhere | read/grep/`ast_grep`/`ast_edit`/`lsp` |
| **Context7** (`README.md:173`) | Yes | Keep | no version-pinned library-docs tool |
| **Tavily** (`README.md:174`) | Yes | Redundant | `web_search` already chains Tavily |
| **hallouminate** (`README.md:176`) | Yes | Soft overlap (your call) | `memory` (off by default) |
| **milknado** (`README.md:177`) | Yes | DAGs only (your call) | `todo` (linear, single-active-task) |
| **Serena/LSP** (`README.md:175`) | Yes | Redundant | native `lsp` |

## Native sub-agents + tools across harnesses

Sourced from each vendor's official docs (fetched 2026-06-30). omp is the
reference column.

| Harness | Sub-agent primitive (parallel? / custom?) | Named built-in agents | Native tools | Skills | MCP | Native AST / LSP |
|---|---|---|---|---|---|---|
| **omp** | `task` (+ `job`, `irc`) / yes / yes | task, explore, plan, designer, reviewer, librarian, oracle, quick_task | read, grep, glob, edit, write, **ast_grep**, **ast_edit**, **lsp**, web_search, task, todo, debug, eval, browser, recall/retain | Yes | Yes | **Yes — both** |
| **Claude Code** | `Agent` (was `Task`) / yes (bg, nested, teams) / yes | Explore, Plan, general-purpose, statusline-setup, claude-code-guide | Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Agent, Skill, TodoWrite/Task, NotebookEdit, AskUserQuestion | Yes | Yes | No AST; LSP via plugin |
| **Cursor** | Subagents via `Task` / yes (Agents Window, cloud) / yes | Explore, Bash, Browser | Semantic search, Instant Grep, file search, Read, Edit, Run shell, Web, Fetch Rules, Browser, Image gen, Ask, Task | Yes + Rules (`.mdc`) | Yes | No (grep + semantic) |
| **Codex CLI** | Subagents (multi-agent) / yes (`max_threads` 6) / yes (TOML) | default, worker, explorer | shell, unified exec, web search, view_image, file editing, plan, image gen, bg terminals, multi-agent | Yes + AGENTS.md | Yes (can be MCP server) | No (grep via shell) |
| **opencode** | primary (Build/Plan) + subagents via `task` / yes / yes | Build, Plan / General, Explore, Scout | bash, edit, write, read, grep, glob, list, lsp (exp), apply_patch, skill, todowrite/read, webfetch, websearch, question, task | Yes (claude-compat) | Yes (OAuth) | No AST; LSP experimental flag |
| **Gemini CLI** | Subagents (exposed as tools) / unknown / yes | codebase_investigator, cli_help, generalist, browser_agent | read_file, write_file, replace, glob, grep_search, run_shell_command, web-fetch, web-search, save_memory, todos, planning, ask-user, activate_skill | Yes + GEMINI.md | Yes | No (git grep) |
| **Copilot CLI** | Custom agents (subagent process) / cloud-parallel / yes (`.agent.md`) | Explore, Task, General purpose, Code review, Research, Rubber duck | shell, read, write/edit, mcp, memory, custom-tool, ext-mgmt; web via Research agent | Yes + custom instructions | Yes (GitHub MCP preconfigured) | LSP via `lsp-config.json`; no AST |

Claude Code's `TodoWrite` is disabled by default as of v2.1.142, superseded by
`TaskCreate`/`Get`/`List`/`Update`.

## Cross-cutting reads

1. **Native sub-agents are table stakes.** Every harness ships a spawn
   primitive with parallel fan-out, custom agents, and a read-only/explore
   built-in. easy-cheese's phase-agent abstraction maps onto all of them.
2. **The Agent Skills spec is universal.** All six load `SKILL.md` natively
   (most honor `.claude/skills` and `.agents/skills` compat paths). This is why
   easy-cheese is portable — the bet paid off.
3. **MCP is universal.** Every harness is a full MCP client, so the optional
   MCP nudges work everywhere; they are redundant only where the capability is
   also native.
4. **Native AST/LSP is omp-only.** The single capability gap that justifies
   tilth on the other five harnesses.

## Implication for the cheez-* dependency

This sharpens, rather than reverses, the de-prescription question. "AST-aware
backend (tilth OR native `ast_grep`/`lsp`)" sounds general, but native
`ast_grep`/`lsp` exists only on omp today; on the other five harnesses the
practical options are tilth or `sg` + an LSP plugin, so tilth stays the sane
default there. The cleanest move is a **backend-contract clause**: keep tilth as
the preferred implementation, and add one clause — "if your harness exposes
native `ast_grep`/`sg`, LSP, bounded reads, and anchored/stale-checking edits
(today: omp), those tools satisfy the `cheez-*` backend contract." Decoupling
further would weaken the skill on the five harnesses where tilth is the only
single packaged AST-aware option.

## Provenance

Distilled from the durable research report at the XDG project corpus
(`nudge-surface-vs-harness-natives.md`, out-of-git per
`wiki-conventions.md`), which carries the full citation set and the
omp-specific config levers that do not belong in this portable page. Harness
facts fetched 2026-06-30 from official docs: docs.claude.com/en/docs/claude-code,
cursor.com/docs, developers.openai.com/codex, opencode.ai/docs,
github.com/google-gemini/gemini-cli, docs.github.com/en/copilot.
