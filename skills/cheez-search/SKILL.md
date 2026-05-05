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
