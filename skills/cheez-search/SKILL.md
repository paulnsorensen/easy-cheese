---
name: cheez-search
description: This skill should be used when the user asks to find a symbol, definition, caller, import, or text pattern in the codebase — phrases like "where is X defined", "what calls Y", "find all usages of Z", "trace this function", "find the TODO comments", "search for this error string". Replaces grep / rg / ripgrep / ag / ack / find / fd with AST-aware tilth MCP search for name-shaped and text-shaped queries; use ast-grep (`sg`) only for AST-shape patterns with metavariables tilth cannot express. Use even when the user says "grep", "rg", "ripgrep", "ag", "ack", "fd", or "find" — never call host Grep, Glob, ripgrep, ast-grep, or any shell search directly. If tilth MCP is unavailable, stop and report rather than fall back. Do NOT use for reading whole files (use cheez-read), editing code (use cheez-write), or running tests/builds.
license: MIT
compatibility: Requires tilth MCP server. Optional ast-grep (`sg`) for structural metavariable patterns tilth cannot express.
allowed-tools: mcp__tilth__tilth_search, mcp__tilth__tilth_deps, Bash
---

# cheez-search

> **Hard dependency**: If `mcp__tilth__tilth_search` is unavailable, stop immediately and report
> "tilth MCP server is not loaded — cannot proceed." Do NOT fall back to `Grep`, `Glob`, `rg`,
> or any host tool. Install via `tilth install <host>` (see README "Installing tilth MCP").

## Capability detection

Before the first call, verify tilth is reachable:

1. Check that `mcp__tilth__tilth_search` is in your tool list. If absent, stop and report `"tilth MCP server is not loaded — cannot proceed."`
2. Make a minimal probe call: `tilth_search(query: "tilth", scope: ".")`. If the response is a JSON-RPC error or transport failure, stop and report `"tilth MCP server present but unhealthy: <error>"`.
3. Any other failure (zero matches, malformed regex, etc.) is a **content** issue — proceed normally and report the result.

AST-aware code search via **tilth MCP** (`tilth_search`, `tilth_deps`).
Tree-sitter finds where symbols are **defined** — not just where strings appear.
Understand dependencies instead of blindly grepping.

---

## Examples

### "Where is `handleAuth` defined?"

```
tilth_search(query: "handleAuth", scope: "src/")
```

```text
# Search: "handleAuth" in src/ — 6 matches (2 definitions, 4 usages)

## src/auth.ts:44-89 [definition]
→ [44-89]  export fn handleAuth(req, res, next)
## src/routes/api.ts:34 [usage]
→ [34]   router.use('/api/protected/*', handleAuth);
```

The `[definition]` tag answers the question; usages come along for free.

### "What calls `validateToken`?"

```
tilth_search(query: "validateToken", kind: "callers", scope: ".")
```

```text
# Callers: "validateToken" — 3 call sites

## src/auth.ts:62 [usage] in handleAuth
→ [62]   const claims = validateToken(token);

## src/middleware/admin.ts:18 [usage] in requireAdmin
→ [18]   if (!validateToken(req.headers.authorization)) return next(403);
```

`kind: "callers"` filters out comments and strings — only real call sites.

### "Find any TODO that mentions retries"

```
tilth_search(query: "TODO.*retry", kind: "regex", scope: "src/")
```

Use `kind: "regex"` for pattern matches across content; bound the scope to
keep the cost down.

---

## Core Principle: Definitions First

Traditional grep finds text matches. tilth_search finds **semantic matches**:
- Definitions: where a symbol is declared
- Usages: where it's called or referenced
- Implementations: where interfaces are implemented

Each match includes its surrounding file structure, so you know what you're
looking at without a second read.

**Why this matters:**
- "handleAuth" appears 47 times, but it's DEFINED in one place
- tilth shows the definition first, then usages ranked by relevance
- You understand the code faster with fewer tool calls

---

## Scope: when tilth, when not

`tilth_search` owns **code in tracked, parseable source files** (Rust, TypeScript/TSX/JS, Python, Go, Java, Scala, C/C++, Ruby, PHP, C#, Swift). Symbol-shaped queries, callers, content, and bounded regex inside the tree all stay here.

### Scope and freshness

The tilth MCP server is launched against **one repository** — whatever directory the harness booted it in. There is no persistent index: tilth walks the working tree on demand, parses files with Tree-sitter, and respects `.gitignore`. Practical consequences:

- No startup wait, no rebuild step, no staleness — your last save is what tilth sees on the next call.
- Cannot reach files outside that one tree (sibling worktrees, `~/...`, system paths, dependency caches like `node_modules` or `.cargo/registry`).
- Cannot answer cross-repo questions in one call. For that, see *When code-review-graph beats tilth* below.

### When NOT to invoke `/cheez-search`

Inside `/cheez-search`, the contract is hard: tilth-only, no host search fallback. The questions below are **out of scope** for the skill — don't enter cheez-search for them in the first place. They're listed here so workflow skills know where to route instead, consistent with the README rule "anything that touches source code goes through cheez-*; everything else stays on host tools".

| Question (don't use cheez-search) | Route to | Why |
|-----------------------------------|----------|-----|
| Pattern with metavars (`JSON.parse(JSON.stringify($X))`) | `sg` (ast-grep) — sanctioned escape, callable from cheez-search via Bash | AST shapes tilth can't express |
| External library docs ("how does React's `useEffect` work?") | `/briesearch` (Context7) | Not your code; live vendor docs |
| Plain non-code text at scale (logs, build outputs, large CSVs) | host `Bash` with `rg`, `jq`, `awk`, `head`/`tail` from the calling workflow skill | Tree-sitter parsing wastes tokens here; format-specific tools win |
| Files outside the repo (system paths, `~/Library`, `/etc`) | host `Grep` / `Bash` from the calling workflow skill | tilth is repo-scoped (see above) |

If you find yourself wanting `grep` *for code in this repo*, that's the signal to stay in cheez-search and the tilth-only contract holds. If the question is non-code or out-of-tree, the calling workflow skill should answer it directly with its own host tools — never break the cheez-search contract by reaching for host search inside this skill.

### When LSP beats tilth (if your harness has one)

**easy-cheese does not install LSP** — it is whatever language servers your harness already exposes (Claude Code LSP plugins, Zed / VS Code language servers, etc.). When an LSP is reachable for the file's language and the question is **type-grounded**, prefer the LSP method over tilth. Tree-sitter sees syntax, not types — it cannot disambiguate `var x = GetValue()` (keyword or type?) or pick between two `pop` functions imported from different modules. LSP runs the actual language server and resolves these.

| Question | LSP method (when available) | Why LSP wins |
|----------|------------------------------|--------------|
| "What's the resolved return type / generic instantiation of X?" | `textDocument/hover` | tilth sees syntax, not types — hover returns the resolved signature |
| "Who implements interface / trait / abstract class Y?" | `textDocument/implementation` | Honors aliased imports, generics, and re-exports; tilth's name match misses these |
| "Where is this exact symbol used, accounting for shadowing and module scope?" | `textDocument/references` | Scope-respecting; tilth's callers query is name-shaped |
| "Where is the *type* (not the value) of X declared?" | `textDocument/typeDefinition` | Resolves through type aliases and generics |
| "Are there type errors in this file?" | `textDocument/diagnostic` / pull-diagnostic | Only LSP runs the language server's typechecker |

If no LSP is installed for the language, or the file is in a broken / incomplete state where the server cannot resolve, fall back to tilth — `tilth_search` still finds the symbol by name even when no semantic resolution is possible. tilth also wins on speed at scale, polyglot queries (one call across Rust + TS + Python), error-tolerant parses, and content / regex queries that LSP does not index.

### When Serena beats tilth (if your harness has it)

[Serena](https://github.com/oraios/serena) is an LSP-driven MCP that exposes the LSP queries above as named tools. If `mcp__serena__find_symbol` is in your tool list, prefer these concrete calls over the abstract LSP methods — same semantics, no IDE round-trip:

| Question | Serena tool | Why it beats tilth |
|----------|-------------|--------------------|
| "Who *really* references X, accounting for aliased imports and shadowing?" | `mcp__serena__find_referencing_symbols` | Type-aware xrefs; tilth's `kind: "callers"` is name-shaped |
| "What implements interface / trait Y?" | `mcp__serena__find_implementations` | Honors generics and re-exports; tilth surfaces every textual match |
| "Where is the declaration of X (following imports)?" | `mcp__serena__find_declaration` | Walks the import graph; tilth returns every definition with that name |
| "Find symbol X across the project, semantically" | `mcp__serena__find_symbol` | LSP-indexed; pair with `get_symbols_overview` for a file's symbol table |

Capability detection: if `mcp__serena__find_symbol` is absent, fall back to `tilth_search` and note "Serena unavailable" in evidence — do not pretend the xref was type-validated. Serena requires `.serena/project.yml` in the repo; if missing, treat it as unconfigured rather than broken. Stay on tilth for polyglot one-call queries, content / regex search, and any case where the language server can't resolve (broken or generated code).

### When code-review-graph beats tilth (if your harness has it)

[`code-review-graph`](https://github.com/tirth8205/code-review-graph) is a separate, optional MCP that builds a **persistent** call graph of one or more repositories with Tree-sitter, Louvain communities, betweenness-centrality, and (with the `[embeddings]` extra) vector embeddings. Where tilth answers "where is `handleAuth`?", code-review-graph answers "what code is *about* authentication, ranked by importance and reach across all my repos?"

It wins on five questions tilth structurally cannot answer:

| Question | code-review-graph tool | Why tilth can't |
|----------|------------------------|-----------------|
| Find code by *meaning*, not name ("rate-limiting logic", "session expiry handling") | `semantic_search_nodes_tool` | Embeddings rank by concept; tilth only matches identifiers and literal text |
| Search across *multiple* repos in one call | `cross_repo_search_tool` | tilth is scoped to one tree per MCP session |
| Risk-weighted blast radius (which callers actually matter, by centrality) | `get_impact_radius_tool`, `get_review_context_tool` | `tilth_deps` returns raw imports; code-review-graph weights them by graph centrality |
| Architecture framing for a large diff (hubs, bridges, communities) | `get_architecture_overview_tool`, `get_hub_nodes_tool`, `get_bridge_nodes_tool`, `list_communities_tool` | tilth has no global graph view |
| Affected execution flows for a change | `get_affected_flows_tool` | tilth follows callers one hop at a time; this returns full flows |

**Before the first query — refresh the graph via MCP.** code-review-graph keeps a persistent graph that goes stale between sessions. From inside an agent, prefer the MCP tools over the CLI:

- Call `build_or_update_graph_tool` once at the start of a run. It's incremental — on a warm repo this is fast.
- If you'll use `semantic_search_nodes_tool` *or* you've added concept-shaped code since the last embed, also call `embed_graph_tool` once. Embedding is the slow step — skip it otherwise.

The CLI equivalents (`code-review-graph build` / `embed`) are for first-time setup; inside a run, the MCP tools let the agent own the lifecycle.

**When `semantic_search_nodes_tool` beats tilth.** Reach for it when the question is concept-shaped, not name-shaped:

- **Steel threads** — trace a feature end-to-end when each layer names the concept differently (controller → service → repo → migration → telemetry). tilth makes you guess the next layer's vocabulary; embeddings surface the chain.
- **Shared concepts under divergent names** — "where do we handle idempotency?" when the code uses `dedupeKey`, `requestSig`, `OnceToken`. Grep is blind to the concept; embeddings find it.
- **Vocabulary mismatch between spec and code** — product says "session continuity", code says `KeepaliveToken`. Map the stakeholder term to the implementation without an SME.
- **Analog mining** — before adding another retry / rate-limit / cache layer, ask what already exists under different names.
- **Cross-repo concept discovery** — pair with `cross_repo_search_tool` to find auth (or any concept) across services that named it differently.
- **Onboarding orientation** — "what's in this repo for observability?" returns conceptually adjacent nodes ranked by graph centrality. Faster first read than walking imports.

**Stay on tilth when** you know the symbol name; you need literal text or regex; you're doing a one-hop caller walk; the branch is hot and you haven't re-embedded; or the change is a mechanical rename or move.

**Two gotchas.** Ranking blends similarity with graph centrality — `semantic_search_nodes_tool` biases toward hub nodes, sometimes against the leaf where the bug actually lives; after a hit, follow callers in tilth. Default embedding model is `all-MiniLM-L6-v2` (384-dim), which blurs nuanced distinctions like "session timeout" vs "session revocation" — override via `CRG_EMBEDDING_MODEL` if your domain needs it.

If code-review-graph is unavailable, the cheez-search fallbacks are: name-shaped questions stay on tilth; semantic / cross-repo / architecture questions either degrade to a manual `tilth_deps` + `kind: "callers"` walk or get noted as unavailable evidence (cap confidence at `speculating`).

---

## Choose your search kind

All six rows below are first-class — picking the right one is the difference
between one call and a long grep walk.

| Goal | Tool | Example |
|------|------|---------|
| Find where a symbol is defined / used | `tilth_search` (default `kind: "symbol"`) | `tilth_search(query: "handleAuth", scope: "src/")` |
| Find every call site of a function | `tilth_search(kind: "callers")` | `tilth_search(query: "validateToken", kind: "callers")` |
| Find literal strings, TODOs, error messages | `tilth_search(kind: "content")` | `tilth_search(query: "TODO: fix", kind: "content")` |
| Find lines matching a regex | `tilth_search(kind: "regex")` | `tilth_search(query: "rate.?limit", kind: "regex")` |
| Match an AST shape (template with metavars) | `sg` (ast-grep, via Bash) | `sg --lang typescript -p 'JSON.parse(JSON.stringify($X))' --json src/` |
| Module import / blast-radius graph | `tilth_deps` | `tilth_deps(path: "src/auth.ts")` |

**Rule of thumb:** stay in tilth for anything name-shaped or text-shaped.
Drop to `sg` only when the pattern needs structural metavariables (`$X`,
`$$$BODY`) that tilth can't express.

---

## MCP Tool Reference

### tilth_search — Symbol and Content Search

**Basic symbol search:**
```
tilth_search(query: "handleAuth", scope: "src/")
```

**Output:**
```
# Search: "handleAuth" in src/ — 6 matches (2 definitions, 4 usages)

## src/auth.ts:44-89 [definition]
  [24-42]  fn validateToken(token: string)
→ [44-89]  export fn handleAuth(req, res, next)
  [91-120] fn refreshSession(req, res)

  44 │ export function handleAuth(req, res, next) {
  45 │   const token = req.headers.authorization?.split(' ')[1];
  ...
  88 │   next();
  89 │ }

  ── calls ──
  validateToken  src/auth.ts:24-42  fn validateToken(token: string): Claims | null
  refreshSession  src/auth.ts:91-120  fn refreshSession(req, res)

## src/routes/api.ts:34 [usage]
→ [34]   router.use('/api/protected/*', handleAuth);
```

**Key features:**
- `[definition]` vs `[usage]` — know what you're looking at
- Context lines show surrounding structure (what else is in this file)
- `── calls ──` footer shows what the function calls (one-hop callees)
- Expanded source blocks include full implementation

---

## Multi-Symbol Search

Trace across files in one call:

```
tilth_search(query: "ServeHTTP, HandlersChain, Next", scope: ".")
```

Each symbol gets its own result block. The expand budget is shared — at least
one expansion per symbol, deduplicated across files.

---

## Callers Query — Find All Call Sites

Find all places that call a specific function using structural tree-sitter
matching (not text search):

```
tilth_search(query: "isTrustedProxy", kind: "callers", scope: ".")
```

**Why this beats grep:** only finds actual calls, not comments or string literals.
Shows the calling function context.

---

## Content Search — Strings and Comments

Search for text that isn't a code symbol:

```
tilth_search(query: "TODO: fix", kind: "content", scope: ".")
```

Use content search for: TODOs, FIXMEs, NOTEs, error messages, specific literal strings.

---

## Regex Search — `kind: "regex"`

For patterns that aren't a single literal:

```
tilth_search(query: "rate.?limit", kind: "regex", scope: ".")
tilth_search(query: "FIXME\\(.*?\\):", kind: "regex", scope: "src/")
```

- Full regex syntax — alternation, character classes, lookarounds depending on the engine.
- Use `glob` to bound the file set; regex is the most expensive `kind`.
- Don't wrap the pattern in `/.../` delimiters — pass the bare regex.

---

## AST-shape Patterns — ast-grep fallback

tilth covers names and text. For *shapes* with metavariables (`$X`, `$$$BODY`)
that tilth cannot express, drop to `sg` (ast-grep) via Bash. This is the
**only** sanctioned shell escape from cheez-search. The same escape covers
structural codemods via `sg --rewrite` (dry-run first; `tilth_edit` remains
the default for one-off block edits).

For metavar pattern syntax, the language matrix, hard rules for safe `sg`
invocations (`--lang`, `--json`, no `--interactive`, path validation, scope
filters), pitfalls (CST-not-AST, metavar binding, strict vs lenient), and the
codemod dry-run protocol, see
[`references/sg-patterns.md`](references/sg-patterns.md).

---

## Glob Filtering

```
# Only Rust files
tilth_search(query: "handleAuth", scope: ".", glob: "*.rs")

# Exclude test files
tilth_search(query: "handleAuth", scope: ".", glob: "!*.test.ts")

# Multiple extensions
tilth_search(query: "handleAuth", scope: ".", glob: "*.{go,rs}")
```

---

## Context Parameter — Boost Nearby Results

When editing a file, pass it as context to boost related results:

```
tilth_search(query: "validateToken", scope: ".", context: "src/auth.ts")
```

---

## Expand Budget — Control Detail Level

```
# Default: 2 expansions
tilth_search(query: "handleAuth", scope: ".")

# More detail
tilth_search(query: "handleAuth", scope: ".", expand: 5)

# Compact (outlines only)
tilth_search(query: "handleAuth", scope: ".", expand: 0)
```

---

## tilth_deps — Dependency Graph

```
tilth_deps(path: "src/auth.ts")
```

Use **only** before refactoring (rename, signature change, removal). For
output format, scope rules, and the symbol-vs-file distinction, see
[`references/tilth-deps.md`](references/tilth-deps.md).

---

## Session Deduplication

tilth tracks what you've already seen:
- Previously expanded definitions show `[shown earlier]`
- Saves tokens when revisiting symbols
- Forces you to reference your notes instead of re-reading

---

## Common Patterns

```
# "Where is X defined?"
tilth_search(query: "AuthManager", scope: ".")
# Look for [definition] results

# "What calls X?"
tilth_search(query: "validateToken", kind: "callers", scope: ".")

# "What does X call?"
tilth_search(query: "handleAuth", scope: ".", expand: 1)
# Check the ── calls ── footer

# "Find all implementations of an interface"
tilth_search(query: "UserRepository", scope: ".", kind: "symbol")
# Implementations show as [impl] tags

# "Search error messages"
tilth_search(query: "invalid token format", kind: "content", scope: ".")

# "What depends on this module?"
tilth_deps(path: "src/auth/index.ts")
# Check ── imported by ── section
```

---

## Tree-sitter Advantages

| Grep finds... | tilth_search finds... |
|---------------|----------------------|
| All occurrences of text | Definitions vs usages |
| No structure awareness | File context (what else is nearby) |
| No call understanding | Callee resolution in results |
| False positives in strings | Only semantic code matches |

**Languages supported:** Rust, TypeScript, TSX, JavaScript, Python, Go, Java, Scala, C, C++, Ruby, PHP, C#, Swift.

---

## DO NOT

- **DO NOT use grep / rg / ripgrep / ag / ack** — use `tilth_search`. `sg` (ast-grep) is the *only* sanctioned shell escape, and only for AST-shape patterns with metavariables tilth can't express.
- **DO NOT use find / fd to locate files by name pattern** — use `tilth_files` (cheez-read). `find` for non-name predicates (size, mtime, perms) is fine outside code work, but redirect anything code-related back through cheez-*.
- **DO NOT use ast-grep (`sg`) for name-shaped or text queries** — that's `tilth_search` territory. `sg` is for structural patterns with metavars (`$X`, `$$$BODY`) only.
- **DO NOT blind text search** — use a semantic `kind` (`symbol`, `callers`, `content`, `regex`) before reaching for `sg`.
- **DO NOT re-read expanded results** — they're already shown.
- **DO NOT use for file reading** — use cheez-read.
- **DO NOT use for editing** — use cheez-write.
- **DO NOT overuse expand** — start with default, increase if needed.

---

## What This Skill Doesn't Do

- **Read entire files** — use cheez-read.
- **Edit code** — use cheez-write.
- **Run tests** — use test/build skills.
- **Git operations** — use git/gh skills.
