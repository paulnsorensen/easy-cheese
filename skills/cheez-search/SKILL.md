---
name: cheez-search
description: Search code via an AST-aware backend -- tilth MCP by default, or harness-native `ast_grep`/`sg` plus LSP when available -- finding symbols, definitions, callers, imports, and text while replacing shell search tools. Use when the user asks to find a symbol, definition, caller, import, or text pattern -- phrases like "where is X defined", "what calls Y", "find all usages of Z", "trace this function", "find the TODO comments", "search for this error string". Use even when the user says "grep", "rg", "ripgrep", "ag", "ack", "fd", or "find". If no AST-aware backend is available, stop and report rather than falling back to plain text search. Do NOT use for reading whole files (use cheez-read), editing code (use cheez-write), or running tests/builds.
license: MIT
compatibility: Prefers tilth MCP. Harness-native `ast_grep`/`sg` and LSP are acceptable when they satisfy the same symbol/caller/structural-search contract.
allowed-tools: mcp__tilth__tilth_search, mcp__tilth__tilth_deps, Bash, AST Grep, LSP
---

# cheez-search

> **Backend contract**: use an AST-aware code-search backend. Prefer tilth MCP because it returns symbols, callers, text matches, and dependency context in one repo-scoped surface. Native `ast_grep`/`sg` and LSP tools are acceptable when they answer the same semantic question more directly.

## Backend detection

Before the first call, choose the strongest available backend:

1. If `mcp__tilth__tilth_search` is in the tool list, make a minimal probe call: `tilth_search(queries: [{query: "tilth"}])`. If the response is a JSON-RPC error or transport failure, stop and report `"tilth MCP server present but unhealthy: <error>"` unless a native AST/LSP backend is available.
2. For structural patterns with metavariables, use native `sg`/ast-grep directly when available; tilth content/regex search is the wrong abstraction for that shape.
3. For type-grounded definitions, references, renames, and server-known refactors, use LSP when available; it follows shadowing, overloads, and re-exports better than text search.
4. If no AST-aware or LSP backend exists, stop and report `"no AST-aware code search backend is available — cannot proceed."`

**Note:** pass `root` (your absolute checkout directory) whenever tilth `scope` is relative — the server's cwd is frozen at startup and cannot resolve relative paths without an explicit `root`.

---

## Examples

### "Where is `handleAuth` defined?"

```
tilth_search(queries: [{query: "handleAuth"}], scope: "src/", root: "/checkout/root")
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
tilth_search(queries: [{query: "validateToken", kind: "callers"}], scope: ".", root: "/checkout/root")
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
tilth_search(queries: [{query: "TODO.*retry", kind: "regex"}], scope: "src/", root: "/checkout/root")
```

Use `kind: "regex"` for pattern matches across content; bound the scope to
keep the cost down.

---

## Scope: when to use the code-search backend, when not

`cheez-search` owns **code in tracked, parseable source files** (Rust, TypeScript/TSX/JS, Python, Go, Java, Scala, C/C++, Ruby, PHP, C#, Swift). Symbol-shaped queries, callers, content, bounded regex, AST-shape patterns, and type-grounded lookups stay in an AST/LSP backend.

### Scope and freshness

Use the backend scoped to the active repository and fresh on disk. Tilth walks the working tree on demand and respects `.gitignore`; native `sg` and LSP qualify when they see the current checkout and answer the requested semantic shape.

Practical consequences:

- No stale indexes: if a backend needs a refresh before it sees current files, refresh or choose a fresher backend.
- Do not use repo-scoped backends for sibling worktrees, system paths, or dependency caches unless the backend explicitly supports that scope.
- Route cross-repo questions before entering cheez-search.

### When NOT to invoke `/cheez-search`

These questions are **out of scope** -- don't enter cheez-search for them; the table tells the calling workflow skill where to route instead.

| Question (don't use cheez-search) | Route to | Why |
|-----------------------------------|----------|-----|
| Pattern with metavars (`JSON.parse(JSON.stringify($X))`) | `sg` (ast-grep) — sanctioned escape, callable from cheez-search via Bash | AST shapes tilth can't express |
| External library docs ("how does React's `useEffect` work?") | `/briesearch` (Context7) | Not your code; live vendor docs |
| Plain non-code text at scale (logs, build outputs, large CSVs) | host `Bash` with `rg`, `jq`, `awk`, `head`/`tail` from the calling workflow skill | Tree-sitter parsing wastes tokens here; format-specific tools win |
| Files outside the repo (system paths, `~/Library`, `/etc`) | host `Grep` / `Bash` from the calling workflow skill | tilth is repo-scoped (see above) |

### Route out before entering (type-grounded)

Name-shaped queries stay in tilth. For type-grounded questions, route out before entering cheez-search -- see [`references/routing.md`](references/routing.md) for LSP and Serena routing tables.

---

## Choose your search kind

For code navigation (where is X / what calls Y / blast radius): start with `kind:symbol` to find the definition, then `kind:callers` for call sites. Fall to `content`/`regex` only when you don't have a symbol name.

| Goal | Tool | Example |
|------|------|---------|
| Find where a symbol is defined / used | `tilth_search` (default `kind: "symbol"`) | `tilth_search(queries: [{query: "handleAuth"}], scope: "src/", root: "/checkout/root")` |
| Find every call site of a function | `tilth_search(kind: "callers")` | `tilth_search(queries: [{query: "validateToken", kind: "callers"}])` |
| Find literal strings, TODOs, error messages | `tilth_search(kind: "content")` | `tilth_search(queries: [{query: "error message", kind: "content"}])` |
| Find lines matching a regex | `tilth_search(kind: "regex")` | `tilth_search(queries: [{query: "rate.?limit", kind: "regex"}])` |
| Match an AST shape (template with metavars) | `sg` (ast-grep, via Bash) | `sg --lang typescript -p 'JSON.parse(JSON.stringify($X))' --json src/` |
| Module import / blast-radius graph | `tilth_deps` | `tilth_deps(path: "src/auth.ts")` |

**Rule of thumb:** stay in tilth for anything name-shaped or text-shaped.
Drop to `sg` only when the pattern needs structural metavariables (`$X`,
`$$$BODY`) that tilth can't express.

---

## MCP Tool Reference

Full invocation shapes, parameter options, and per-kind worked examples are in
[`references/tilth-search-reference.md`](references/tilth-search-reference.md).

### AST-shape Patterns -- ast-grep fallback

For shapes with metavars (`$X`, `$$$BODY`) drop to `sg` via Bash -- the only sanctioned shell escape, covering structural codemods via `sg --rewrite`. For syntax, the language matrix, safe-invocation rules, pitfalls, and the codemod dry-run protocol, see [`references/sg-patterns.md`](references/sg-patterns.md).

---

## DO NOT and Scope Limits

- **DO NOT use grep / rg / ripgrep / ag / ack / find / fd for code** -- use an AST-aware backend. `sg` is allowed for AST-shape metavar patterns and codemods; LSP is preferred for type-grounded definitions, references, renames, and code actions. `find` for non-name predicates (size, mtime, perms) is fine outside code work.
- **DO NOT blind text search** -- pick a semantic `kind` (`symbol`, `callers`, `content`, `regex`) first.
- **DO NOT re-read expanded results** -- they're already shown.
- **DO NOT overuse expand** -- start with default, increase if needed.
- **Not for reading entire files** -- use cheez-read.
- **Not for editing code** -- use cheez-write.
- **Not for running tests** -- use test/build skills.
- **Not for git operations** -- use git/gh skills.
