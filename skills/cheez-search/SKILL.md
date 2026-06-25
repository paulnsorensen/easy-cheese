---
name: cheez-search
description: Search code via AST-aware tilth MCP -- finds symbols, definitions, callers, imports, and text, replacing shell search tools. Use when the user asks to find a symbol, definition, caller, import, or text pattern -- phrases like "where is X defined", "what calls Y", "find all usages of Z", "trace this function", "find the TODO comments", "search for this error string". Use ast-grep (`sg`) only for AST-shape patterns with metavariables tilth cannot express. Use even when the user says "grep", "rg", "ripgrep", "ag", "ack", "fd", or "find" -- never call host Grep, Glob, ripgrep, ast-grep, or any shell search directly. If tilth MCP is unavailable, stop and report rather than fall back. Do NOT use for reading whole files (use cheez-read), editing code (use cheez-write), or running tests/builds.
license: MIT
compatibility: Requires tilth MCP server. Optional ast-grep (`sg`) for structural metavariable patterns tilth cannot express.
allowed-tools: mcp__tilth__tilth_search, mcp__tilth__tilth_deps, Bash
---

# cheez-search

> **Hard dependency**: tilth MCP is required. Install via `tilth install <host>` (see README "Installing tilth MCP").

## Capability detection

Before the first call, verify tilth is reachable:

1. Check that `mcp__tilth__tilth_search` is in your tool list. If absent, stop and report `"tilth MCP server is not loaded — cannot proceed."`
2. Make a minimal probe call: `tilth_search(queries: [{query: "tilth"}])`. If the response is a JSON-RPC error or transport failure, stop and report `"tilth MCP server present but unhealthy: <error>"`.
3. Any other failure (zero matches, bad regex) is a content issue - proceed.

**Note:** pass `root` (your absolute checkout directory) whenever `scope` is relative — the server's cwd is frozen at startup and cannot resolve relative paths without an explicit `root`.

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

## Scope: when tilth, when not

`tilth_search` owns **code in tracked, parseable source files** (Rust, TypeScript/TSX/JS, Python, Go, Java, Scala, C/C++, Ruby, PHP, C#, Swift). Symbol-shaped queries, callers, content, and bounded regex inside the tree all stay here.

### Scope and freshness

The tilth MCP server is launched against **one repository** — whatever directory the harness booted it in. There is no persistent index: tilth walks the working tree on demand, parses files with Tree-sitter, and respects `.gitignore`. Practical consequences:

- No startup wait, no rebuild step, no staleness — your last save is what tilth sees on the next call.
- Cannot reach files outside that one tree (sibling worktrees, `~/...`, system paths, dependency caches like `node_modules` or `.cargo/registry`).
- Cannot answer cross-repo questions in one call. For that, see [*When code-review-graph beats tilth*](references/routing.md#when-code-review-graph-beats-tilth-if-your-harness-has-it).

### When NOT to invoke `/cheez-search`

These questions are **out of scope** -- don't enter cheez-search for them; the table tells the calling workflow skill where to route instead.

| Question (don't use cheez-search) | Route to | Why |
|-----------------------------------|----------|-----|
| Pattern with metavars (`JSON.parse(JSON.stringify($X))`) | `sg` (ast-grep) — sanctioned escape, callable from cheez-search via Bash | AST shapes tilth can't express |
| External library docs ("how does React's `useEffect` work?") | `/briesearch` (Context7) | Not your code; live vendor docs |
| Plain non-code text at scale (logs, build outputs, large CSVs) | host `Bash` with `rg`, `jq`, `awk`, `head`/`tail` from the calling workflow skill | Tree-sitter parsing wastes tokens here; format-specific tools win |
| Files outside the repo (system paths, `~/Library`, `/etc`) | host `Grep` / `Bash` from the calling workflow skill | tilth is repo-scoped (see above) |

### Route out before entering (type / concept / cross-repo)

Name-shaped queries stay in tilth. For type-grounded, concept-shaped, or cross-repo questions, route out before entering cheez-search -- see [`references/routing.md`](references/routing.md) for LSP, Serena, and code-review-graph routing tables.

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

- **DO NOT use grep / rg / ripgrep / ag / ack / find / fd for code** -- use `tilth_search`; to find files by name, use `/cheez-read` (its `tilth_list`). `find` for non-name predicates (size, mtime, perms) is fine outside code work. `sg` is the only sanctioned shell escape, and only for AST-shape metavar patterns.
- **DO NOT blind text search** -- pick a semantic `kind` (`symbol`, `callers`, `content`, `regex`) first.
- **DO NOT re-read expanded results** -- they're already shown.
- **DO NOT overuse expand** -- start with default, increase if needed.
- **Not for reading entire files** -- use cheez-read.
- **Not for editing code** -- use cheez-write.
- **Not for running tests** -- use test/build skills.
- **Not for git operations** -- use git/gh skills.
