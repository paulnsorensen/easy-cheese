---
name: cheez-search
description: This skill should be used when the user asks to find a symbol, definition, caller, import, impact radius, or text pattern in the codebase — phrases like "where is X defined", "what calls Y", "find all usages of Z", "trace this function", "what breaks if I change this", "find the TODO comments", "search for this error string". Replaces grep / rg / ripgrep / ag / ack / find / fd with graph/AST-aware MCP search: prefer code-review-graph MCP for caller/callee/dependency/impact/review-context questions when available, use tilth MCP for direct symbol/content/regex lookup and reading/edit anchors, and use ast-grep (`sg`) only for AST-shape patterns with metavariables neither MCP can express. Use even when the user says "grep", "rg", "ripgrep", "ag", "ack", "fd", or "find" — never call host Grep, Glob, ripgrep, ast-grep, or any shell search directly. If tilth MCP is unavailable, stop and report rather than fall back. Do NOT use for reading whole files (use cheez-read), editing code (use cheez-write), or running tests/builds.
license: MIT
compatibility: Requires tilth MCP server. Encourages optional code-review-graph MCP for graph-shaped searches. Optional ast-grep (`sg`) for structural metavariable patterns neither MCP can express.
allowed-tools: mcp__tilth__tilth_search, mcp__tilth__tilth_deps, mcp__code-review-graph__build_or_update_graph_tool, mcp__code-review-graph__get_minimal_context_tool, mcp__code-review-graph__query_graph_tool, mcp__code-review-graph__semantic_search_nodes_tool, mcp__code-review-graph__get_impact_radius_tool, mcp__code-review-graph__get_review_context_tool, mcp__code-review-graph__detect_changes_tool, Bash
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

Graph/AST-aware code search via **code-review-graph MCP** and **tilth MCP**.
Tree-sitter finds where symbols are **defined** — not just where strings appear.
Understand callers, callees, dependencies, tests, and blast radius instead of
blindly grepping.

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

code-review-graph adds **relationship matches**:
- Callers/callees: which code depends on a function or class
- Imports/dependencies: which modules pull a file into their blast radius
- Review context: changed files, affected flows, and test gaps

Each match includes its surrounding file structure, so you know what you're
looking at without a second read.

**Why this matters:**
- "handleAuth" appears 47 times, but it's DEFINED in one place
- tilth shows the definition first, then usages ranked by relevance
- You understand the code faster with fewer tool calls

---

## Choose your search kind

All six rows below are first-class — picking the right one is the difference
between one call and a long grep walk.

| Goal | Tool | Example |
|------|------|---------|
| Get compact orientation before graph work | `get_minimal_context_tool` | `get_minimal_context_tool()` |
| Build/update the review graph | `build_or_update_graph_tool` | `build_or_update_graph_tool()` |
| Find where a symbol is defined / used | `tilth_search` (default `kind: "symbol"`) | `tilth_search(query: "handleAuth", scope: "src/")` |
| Find every call site of a function | `query_graph_tool` when available; otherwise `tilth_search(kind: "callers")` | `query_graph_tool(pattern: "callers_of", target: "validateToken")` |
| Find what a function/class calls | `query_graph_tool` | `query_graph_tool(pattern: "callees_of", target: "handleAuth")` |
| Find literal strings, TODOs, error messages | `tilth_search(kind: "content")` | `tilth_search(query: "TODO: fix", kind: "content")` |
| Find lines matching a regex | `tilth_search(kind: "regex")` | `tilth_search(query: "rate.?limit", kind: "regex")` |
| Match an AST shape (template with metavars) | `sg` (ast-grep, via Bash) | `sg --lang typescript -p 'JSON.parse(JSON.stringify($X))' --json src/` |
| Module import / blast-radius graph | `get_impact_radius_tool` or `detect_changes_tool` when available; otherwise `tilth_deps` | `get_impact_radius_tool(changed_files: ["src/auth.ts"])` |
| Review-scoped context for a diff | `get_review_context_tool` | `get_review_context_tool()` |
| Search entities by name/meaning | `semantic_search_nodes_tool` | `semantic_search_nodes_tool(query: "auth token validation")` |

**Rule of thumb:** stay in MCP. Use code-review-graph for graph-shaped questions
(callers, callees, dependencies, impact radius, review context, affected tests).
Use tilth for direct name-shaped or text-shaped lookup and for cheez-read /
cheez-write anchors. Drop to `sg` only when the pattern needs structural
metavariables (`$X`, `$$$BODY`) that neither MCP can express.

---

## MCP Tool Reference

### code-review-graph — Caller, Dependency, and Review Graph

Use code-review-graph before any grep-style fallback when the question is about
relationships rather than raw text.

**Capability detection:**

1. Check whether `mcp__code-review-graph__get_minimal_context_tool` or
   `mcp__code-review-graph__query_graph_tool` is in your tool list.
2. If present, call `get_minimal_context_tool` first for graph status and compact
   orientation.
3. If the graph is missing or stale and `build_or_update_graph_tool` is
   available, call it before graph queries.
4. If code-review-graph is unavailable, say so once and continue with tilth MCP.
   Do **not** jump to host `rg`, `grep`, or `find`.

**Graph-shaped routing:**

| Need | Preferred code-review-graph tool |
| --- | --- |
| "What calls X?" / "What does X call?" | `query_graph_tool` |
| "What depends on this file/module?" | `query_graph_tool` or `get_impact_radius_tool` |
| "What is affected by this diff?" | `detect_changes_tool`, then `get_review_context_tool` |
| "What context should I read for review?" | `get_review_context_tool` |
| "Find code entities related to this concept" | `semantic_search_nodes_tool` |

Use the returned files/functions as the shortlist for `cheez-read`; do not expand
the search with grep unless both MCP paths fail or the user explicitly asks for a
non-code shell search.

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

Use **only** before refactoring (rename, signature change, removal) when
code-review-graph is unavailable or you need tilth's path-scoped importer list.
For output format, scope rules, and the symbol-vs-file distinction, see
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
query_graph_tool(pattern: "callers_of", target: "validateToken")
# If code-review-graph is unavailable:
tilth_search(query: "validateToken", kind: "callers", scope: ".")

# "What does X call?"
query_graph_tool(pattern: "callees_of", target: "handleAuth")

# "Find all implementations of an interface"
tilth_search(query: "UserRepository", scope: ".", kind: "symbol")
# Implementations show as [impl] tags

# "Search error messages"
tilth_search(query: "invalid token format", kind: "content", scope: ".")

# "What depends on this module?"
get_impact_radius_tool(changed_files: ["src/auth/index.ts"])
# If code-review-graph is unavailable:
tilth_deps(path: "src/auth/index.ts")
```

---

## Tree-sitter Advantages

| Grep finds... | MCP search finds... |
|---------------|----------------------|
| All occurrences of text | Definitions vs usages |
| No structure awareness | File context (what else is nearby) |
| No call understanding | Callee resolution in results |
| No impact model | Callers, imports, affected flows, and test gaps |
| False positives in strings | Only semantic code matches |

**Languages supported:** Rust, TypeScript, TSX, JavaScript, Python, Go, Java, Scala, C, C++, Ruby, PHP, C#, Swift.

---

## DO NOT

- **DO NOT use grep / rg / ripgrep / ag / ack** — use `tilth_search`. `sg` (ast-grep) is the *only* sanctioned shell escape, and only for AST-shape patterns with metavariables tilth can't express.
- **DO NOT use find / fd to locate files by name pattern** — use `tilth_files` (cheez-read). `find` for non-name predicates (size, mtime, perms) is fine outside code work, but redirect anything code-related back through cheez-*.
- **DO NOT use grep / rg to approximate callers, imports, or blast radius** — use code-review-graph first, then tilth MCP if the graph server is unavailable.
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
