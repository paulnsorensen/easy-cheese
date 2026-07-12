---
name: cheez-search
description: Search code through the most precise semantic backend — prefer tilth MCP, with AST search (`sg`) for structural patterns. Use when the user asks to find a symbol, definition, caller, import, or text pattern — phrases like "where is X defined", "what calls Y", "find all usages of Z", "trace this function", "find the TODO comments", "search for this error string". Use even when the user says "grep", "rg", "ripgrep", "ag", "ack", "fd", or "find". Do NOT use for reading whole files (use cheez-read), editing code (use cheez-write), or running tests/builds.
license: MIT
compatibility: Prefers tilth MCP. Harness-native AST search and LSP are acceptable when they answer the requested symbol, caller, structural, or type-grounded question.
allowed-tools: mcp__tilth__tilth_search, mcp__tilth__tilth_deps, Bash
---

# cheez-search

> **Backend contract**: use a semantic code-search backend, not blind text search. Choose the narrowest tool that answers the question.

## Backend detection

Pick the backend by question type:

1. **LSP wins for type-grounded questions:** definitions through imports, references with shadowing/re-exports, hover/type info, implementations, rename planning, and server-known code actions.
2. **AST search / `sg` wins for syntax shapes:** structural patterns with metavariables and repeated syntax-shaped codemods.
3. **tilth MCP wins for broad source search:** symbols, callers, imports, content, bounded regex, and dependency/blast-radius context in one fresh repo scan.

**Note:** every tilth tool takes `cwd` — your absolute checkout directory (the server's own cwd is frozen at startup). In Claude Code a hook injects `cwd` automatically; do not set it. On harnesses without the hook, pass `cwd` explicitly so relative paths and scopes resolve. There is no `root` parameter.

---

## Examples

### "Where is `handleAuth` defined?"

```
tilth_search(queries: [{query: "handleAuth"}], scope: "src/")
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
tilth_search(queries: [{query: "validateToken", kind: "callers"}])
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
tilth_search(queries: [{query: "TODO.*retry", kind: "regex"}], scope: "src/")
```

Use `kind: "regex"` for pattern matches across content; bound the scope to
keep the cost down.

---

## Scope: when to use the code-search backend, when not

`cheez-search` owns **code in tracked, parseable source files** (Rust, TypeScript/TSX/JS, Python, Go, Java, Scala, C/C++, Ruby, PHP, C#, Swift). Symbol-shaped queries, callers, content, bounded regex, AST-shape patterns, and type-grounded lookups stay in an AST/LSP backend.

### Scope and freshness

Use the backend scoped to the active repository and fresh on disk. tilth MCP walks the working tree on demand and respects `.gitignore`; native `sg` and LSP qualify when they see the current checkout and answer the requested semantic shape.

Practical consequences:

- No stale indexes: if a backend needs a refresh before it sees current files, refresh or choose a fresher backend.
- Do not use repo-scoped backends for sibling worktrees, system paths, or dependency caches unless the backend explicitly supports that scope.
- Route cross-repo questions before entering cheez-search.

### When NOT to invoke `/cheez-search`

These questions are **out of scope** -- don't enter cheez-search for them; the table tells the calling workflow skill where to route instead.

| Question (don't use cheez-search) | Route to | Why |
|-----------------------------------|----------|-----|
| Pattern with metavars (`JSON.parse(JSON.stringify($X))`) | `sg` (ast-grep) — sanctioned escape, callable from cheez-search via Bash | AST shapes name/text search can't express |
| External library docs ("how does React's `useEffect` work?") | `/briesearch` (Context7) | Not your code; live vendor docs |
| Plain non-code text at scale (logs, build outputs, large CSVs) | host `Bash` with `rg`, `jq`, `awk`, `head`/`tail` from the calling workflow skill | Tree-sitter parsing wastes tokens here; format-specific tools win |
| Files outside the repo (system paths, `~/Library`, `/etc`) | host `Grep` / `Bash` from the calling workflow skill | cheez-search is repo-scoped (see above) |

### Route out before entering (type-grounded)

Name-shaped queries stay in the semantic search backend chosen for this run (tilth, native AST search, or an equivalent indexed source-search path). For type-grounded questions, route out before entering cheez-search -- see [`references/routing.md`](references/routing.md) for LSP and Serena routing tables.

---

## Choose your search kind

For code navigation (where is X / what calls Y / blast radius): start with `kind:symbol` to find the definition, then `kind:callers` for call sites. Fall to `content`/`regex` only when you don't have a symbol name.

| Goal | Example backend | Example |
|------|-----------------|---------|
| Find where a symbol is defined / used | `tilth_search` symbol kind, native AST symbol search, or LSP definition when type-grounded | See [Examples](#examples) — "Where is `handleAuth` defined?" |
| Find every call site of a function | `tilth_search` callers kind, native AST caller search, or LSP references when type-grounded | See [Examples](#examples) — "What calls `validateToken`?" |
| Find literal strings, TODOs, error messages | content search in the semantic backend | `tilth_search(queries: [{query: "error message", kind: "content"}])` |
| Find lines matching a regex | bounded regex search in the semantic backend | `tilth_search(queries: [{query: "rate.?limit", kind: "regex"}])` |
| Match an AST shape (template with metavars) | `sg` (ast-grep, via Bash) | `sg --lang typescript -p 'JSON.parse(JSON.stringify($X))' --json src/` |
| Module import / blast-radius graph | `tilth_deps`, LSP references/import graph, or equivalent dependency context | `tilth_deps(path: "src/auth.ts")` |

**Rule of thumb:** stay in a semantic source-search backend for name-shaped or text-shaped queries.
Drop to `sg` only when the pattern needs structural metavariables (`$X`,
`$$$BODY`) that the selected backend can't express.

---

## MCP Tool Reference

Full invocation shapes, parameter options, and per-kind worked examples are in
[`references/tilth-search-reference.md`](references/tilth-search-reference.md).

### AST-shape Patterns -- ast-grep fallback

For shapes with metavars (`$X`, `$$$BODY`) drop to `sg` via Bash -- the only sanctioned shell escape, covering structural codemods via `sg --rewrite`. For syntax, the language matrix, safe-invocation rules, pitfalls, and the codemod dry-run protocol, see [`references/sg-patterns.md`](references/sg-patterns.md).

---

## DO NOT and Scope Limits

- **Semantic backend for code search.** `sg` covers AST-shape metavar patterns and codemods; LSP covers type-grounded definitions and references (renames and code actions are edits — route them to cheez-write); `find` stays fine for non-name predicates (size, mtime, perms) outside code work. Do not use grep, rg, ripgrep, ag, ack, find, or fd for code.
- **Expanded results are already shown.** Do not re-read them.
- **Start with the default expand count.** Increase only if needed; do not overuse expand.
- **Read entire files via cheez-read.** Not here.
- **Edit code via cheez-write.** Not here.
- **Run tests via the project's test/build skills.** Not here.
- **Handle git operations via git/gh skills.** Not here.
