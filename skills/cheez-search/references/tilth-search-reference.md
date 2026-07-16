# tilth_search - Worked Examples and Parameters

Detailed invocation shapes, output format, and per-kind parameter reference.
For which kind to pick, see the **Choose your search kind** table in `SKILL.md`.

All examples omit `cwd`: every tilth tool requires it (your absolute checkout
directory), but the Claude Code hook injects it automatically — set it only on
harnesses without the hook. There is no `root` parameter. Omit `scope` to
search the whole checkout; pass it only to narrow to a subdirectory.

---

## tilth_search - Symbol and Content Search

**Basic symbol search:**
```
tilth_search(queries: [{query: "handleAuth"}], scope: "src/")
```

**Output:**
```
# Search: "handleAuth" in src/ — 6 matches (2 definitions, 4 usages)

## src/auth.ts:44-89 [definition]
  [24-42]  fn validateToken(token: string)
→ [44-89]  export fn handleAuth(req, res, next)
  [91-120] fn refreshSession(req, res)

  44 | export function handleAuth(req, res, next) {
  45 |   const token = req.headers.authorization?.split(' ')[1];
  ...
  88 |   next();
  89 | }

  -- calls --
  validateToken  src/auth.ts:24-42  fn validateToken(token: string): Claims | null
  refreshSession  src/auth.ts:91-120  fn refreshSession(req, res)

## src/routes/api.ts:34 [usage]
→ [34]   router.use('/api/protected/*', handleAuth);
```

**Key features:**
- `[definition]` vs `[usage]` -- know what you're looking at
- Context lines show surrounding structure (what else is in this file)
- `-- calls --` footer shows what the function calls (one-hop callees)
- Expanded source blocks include full implementation

---

## Multi-Symbol Search

Trace across files in one call:

```
tilth_search(queries: [{query: "ServeHTTP, HandlersChain, Next"}])
```

Each symbol gets its own result block. The expand budget is shared - at least
one expansion per symbol, deduplicated across files.

---

## Callers Query - Find All Call Sites

Find all places that call a specific function using structural tree-sitter
matching (not text search):

```
tilth_search(queries: [{query: "isTrustedProxy", kind: "callers"}])
```

**Why this beats grep:** only finds actual calls, not comments or string literals.
Shows the calling function context.

---

## Content Search - Strings and Comments

Search for text that isn't a code symbol:

```
tilth_search(queries: [{query: "error: retry limit exceeded", kind: "content"}])
```

Use content search for code-comment annotations, error messages, and specific
literal strings — any text that isn't a code symbol.

---

## Regex Search - `kind: "regex"`

For patterns that aren't a single literal:

```
tilth_search(queries: [{query: "rate.?limit", kind: "regex"}])
```

- Full regex syntax -- alternation, character classes, lookarounds depending on the engine.
- Use `glob` to bound the file set; regex is the most expensive `kind`.
- Don't wrap the pattern in `/.../` delimiters -- pass the bare regex.

---

## Glob Filtering

```
# Only Rust files
tilth_search(queries: [{query: "handleAuth"}], glob: "*.rs")

# Exclude test files
tilth_search(queries: [{query: "handleAuth"}], glob: "!*.test.ts")

# Multiple extensions
tilth_search(queries: [{query: "handleAuth"}], glob: "*.{go,rs}")
```

---

## Context Parameter - Boost Nearby Results

When editing a file, pass it as context to boost related results:

```
tilth_search(queries: [{query: "validateToken"}], context: "src/auth.ts")
```

---

## Expand Budget - Control Detail Level

```
# Default: 2 expansions
tilth_search(queries: [{query: "handleAuth"}])

# More detail
tilth_search(queries: [{query: "handleAuth"}], expand: 5)

# Compact (outlines only)
tilth_search(queries: [{query: "handleAuth"}], expand: 0)
```

---

## tilth_deps - Dependency Graph

```
tilth_deps(path: "src/auth.ts")
```

Use **only** before refactoring (rename, signature change, removal). For
output format, scope rules, and the symbol-vs-file distinction, see
[`references/tilth-deps.md`](tilth-deps.md).

---

## Session Deduplication

tilth tracks what you've already seen:
- Previously expanded definitions show `[shown earlier]`
- Saves tokens when revisiting symbols
- Forces you to reference your notes instead of re-reading

---

## Common navigation workflow

```
# "Find all implementations of an interface"
tilth_search(queries: [{query: "UserRepository", kind: "symbol"}])
# Implementations show as [impl] tags

# "What depends on this module?"
tilth_deps(path: "src/auth/index.ts")
# Check -- imported by -- section
```
