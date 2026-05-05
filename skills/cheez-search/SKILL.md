---
name: cheez-search
description: This skill should be used when the user asks to find a symbol, definition, caller, import, or text pattern in the codebase — phrases like "where is X defined", "what calls Y", "find all usages of Z", "trace this function", "find the TODO comments", "search for this error string". Replaces grep / rg / find / sg with AST-aware tilth MCP search. Use even when the user says "grep" — never call host Grep, Glob, or rg directly. If tilth MCP is unavailable, stop and report rather than fall back.
license: MIT
compatibility: Requires tilth MCP server. Optional ast-grep (`sg`) for structural metavariable patterns tilth cannot express.
allowed-tools: mcp__tilth__tilth_search mcp__tilth__tilth_deps Bash
---

# cheez-search

> **Hard dependency**: If `mcp__tilth__tilth_search` is unavailable, stop immediately and report
> "tilth MCP server is not loaded — cannot proceed." Do NOT fall back to `Grep`, `Glob`, `rg`,
> or any host tool.

AST-aware code search via **tilth MCP** (`tilth_search`, `tilth_deps`).
Tree-sitter finds where symbols are **defined** — not just where strings appear.
Understand dependencies instead of blindly grepping.

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

tilth covers names and text. For *shapes* with metavariables — "any call to
`JSON.parse(JSON.stringify(…))`", "any `for` loop with `time.Sleep` in its
body" — use `sg` (ast-grep) via Bash.

```bash
# AST template: $X is a metavar that matches any single node.
sg --lang typescript -p 'JSON.parse(JSON.stringify($X))' --json src/

# $$$BODY matches a sequence of statements.
sg --lang rust -p 'impl std::fmt::Display for $TYPE { $$$BODY }' --json src/

# Bound the scan; never splice unvalidated user input as the path.
SCOPE=$(realpath "$SCOPE_INPUT")
sg --lang python -p 're.match($PATTERN, $INPUT)' --json "$SCOPE"
```

**When `sg` is the right pick:**
- The pattern needs metavars (`$X`, `$$$BODY`) or specific node kinds.
- You're surveying a structural shape across a directory (anti-pattern sweeps, refactor previews).
- Tree-sitter symbol search would over-match because the *name* isn't fixed.

**Hard rules for sg invocations:**
- Validate any path that flows from user input before splicing it into the command line.
  Reject `;`, `&`, `|`, backtick, `$(`, `>`, `<`, newline. Resolve to an absolute path with
  `realpath` and confirm it sits under the repo root.
- Always pass `--json` and parse defensively — the JSON shape varies between ast-grep versions.
- Filter test/build/vendor directories with `--globs` or by post-filtering JSON.

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

For understanding module relationships (not searching):

```
tilth_deps(path: "src/auth.ts")
```

**Output:**
```
# Dependencies for src/auth.ts

── imports ──
  express        external
  jsonwebtoken   external
  @/config       src/config/index.ts

── imported by ──
  src/routes/api.ts:5
  src/routes/admin.ts:8
  src/middleware/auth.ts:3
```

Use for: understanding blast radius before refactoring, finding consumers of a module, tracing import chains.

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

- **DO NOT use Grep/rg** — use `tilth_search`. `sg` is the *only* sanctioned shell escape, and only for AST-shape patterns tilth can't express.
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
