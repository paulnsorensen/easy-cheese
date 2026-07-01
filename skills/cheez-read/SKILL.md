---
name: cheez-read
description: Read and list files through a freshness-aware code backend — tilth MCP by default, or harness-native structural/LSP-aware tools when they provide equivalent anchors/context. Replaces cat / head / tail / less / more / bat / ls / tree / eza / find / fd / Read / Glob. Use when the user asks to read, view, show, open, or display a file or directory — phrases like "read src/auth.ts", "show me this file", "what's in this directory", "view lines 44-89", "look at the imports". Use even when the user names a shell viewer/lister or says "open the file". If neither tilth nor an equivalent native backend is available, stop and report rather than falling back to plain shell viewers. Do NOT use for searching symbols or text (use cheez-search), editing code (use cheez-write), or git/gh operations.
license: MIT
compatibility: Prefers tilth MCP. Harness-native AST/LSP/read-list tools are acceptable when they provide equivalent freshness, structure, and edit-anchor context.
allowed-tools: mcp__tilth__tilth_read, mcp__tilth__tilth_list, mcp__tilth__tilth_deps, Read, Glob, LSP
---

# cheez-read

## Backend detection

Prefer tilth because it combines repo-scoped listing, smart outlines, and edit anchors. If `mcp__tilth__tilth_read` is available, make a minimal probe call: `tilth_read(paths: ["README.md#1-1"])`. If the response is a JSON-RPC error or transport failure, stop and report `"tilth MCP server present but unhealthy: <error>"` unless the harness has an equivalent native backend.

When tilth is absent, use the harness-native read/list tools only if they preserve the same contract: fresh on-disk content, bounded reads, repo-aware listing, and enough line or snapshot anchors for the next edit. OMP's native read/list/edit stack qualifies. Plain shell viewers (`cat`, `head`, `tail`, `ls`, `find`) do not.

If no backend satisfies that contract, stop and report `"no freshness-aware code read backend is available — cannot proceed."`

---

## Examples

### "Show me `src/auth.ts`"

```
tilth_read(paths: ["src/auth.ts"])
```

Small files come back with full content and a header (`# src/auth.ts (258
lines, ~3.4k tokens) [full]`); large files get the structural outline
automatically.

### "Read the `handleAuth` function by symbol name"

```
tilth_read(paths: ["src/auth.ts#handleAuth"])
```

The `#symbol_name` suffix resolves to the symbol's line range. Use this when you know the name but not the line numbers.

### "Get a stripped outline of a large file before editing"

```
tilth_read(paths: ["src/auth.ts"], mode: "stripped")
```

`mode:stripped` returns the whole file with plain comments and debug logs removed — useful for surveying structure without hash anchors before deciding what to read in full.

### "Read lines 44-89 of `src/auth.ts` to get edit anchors"

```
tilth_read(paths: ["src/auth.ts#44-89"])
```

```text
44:b2c|export function handleAuth(req, res, next) {
45:c3d|  const token = req.headers.authorization?.split(' ')[1];
...
89:e1d|}
```

Hash anchors are emitted automatically — copy `44:b2c` and `89:e1d` and pass them to cheez-write.

### "List every TypeScript file under `src/handlers/`"

```
tilth_list(patterns: ["*.ts"], scope: "src/handlers/")
```

---

## Core Principle: Read Smart, Not More

tilth auto-sizes: small files (< ~6000 tokens) return full, larger files an outline, binary/generated files are skipped.

---

## Scope: when to use the code-read backend, when not

`cheez-read` owns **source code files in tracked, parseable languages** — anything that may later need symbol navigation, edit anchors, or cheez-write edits. Smart outlining, edit-mode anchors, session deduplication, and `.gitignore`-aware listings belong to the backend.

### Scope and freshness

Use a backend scoped to the active repository and fresh on disk. Tilth walks the working tree on demand, parses files with Tree-sitter, and respects `.gitignore`; a harness-native backend must provide comparable freshness and bounded reads before it can stand in.

Practical consequences:

- Prefer a backend that reads the current save, not a stale index.
- Do not use repo-scoped backends for sibling worktrees, system paths, or dependency caches unless the backend explicitly supports that scope.
- For multi-repo reads, the calling workflow skill must route per repo before entering cheez-read.

For when another tool fits better than cheez-read, see [`references/routing.md`](references/routing.md).

---

## Hash anchors

Drilled reads (line range, `#symbol`, or heading) emit `<line>:<hash>|<content>` anchors; plain full-file reads use a `│` (U+2502) separator instead. Reading before editing is mandatory to get current hashes — copy the `<line>:<hash>` portion into cheez-write, where the hash uniquely identifies the line so a stale edit is rejected safely.

---

## tilth_list — Directory Listing

Replaces `ls`, `find`, `pwd`, and the Glob tool.

```
tilth_list(patterns: ["**/*.ts"], scope: "src/")
```

**Output:**
```
src/auth.ts  (~3.4k tokens)
src/routes.ts  (~2.1k tokens)
src/middleware.ts  (~1.8k tokens)
```

Token estimates inform what to read in full vs outline.

Negation works inline: `patterns: ["!*_test.go"]`.

---

## tilth_deps — Blast Radius Check

```
tilth_deps(path: "src/auth.ts")
```

Use **only** before refactoring (rename, signature change, removal). For
output format and the file-vs-symbol distinction, see the shared reference
in cheez-search:
[`../cheez-search/references/tilth-deps.md`](../cheez-search/references/tilth-deps.md).

---

## DO NOT

- **DO NOT use cat / head / tail / less / more / bat** to view code — use a freshness-aware read backend. Hash anchors and outline-vs-full token budgeting only work through the backend.
- **DO NOT use ls / tree / eza / find / fd to enumerate code files** — use a repo-aware listing backend. Token estimates and `.gitignore` filtering only work through the backend.
- **DO NOT use plain host Read or Glob on code paths** unless they are the harness's native freshness-aware backend; otherwise they bypass anchors and structural context.
- **DO NOT re-read files** shown earlier — reference the prior read.
- **DO NOT use to run code or tests** — use the project's build/test skills.
- **DO NOT use to commit** — use git/gh skills.
- **DO NOT ignore hash anchors** — they are required for edits.
