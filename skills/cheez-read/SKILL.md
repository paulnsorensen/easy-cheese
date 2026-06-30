---
name: cheez-read
description: Read and list files via AST-aware tilth MCP — replaces cat / head / tail / less / more / bat / ls / tree / eza / find / fd / Read / Glob. Use when the user asks to read, view, show, open, or display a file or directory — phrases like "read src/auth.ts", "show me this file", "what's in this directory", "view lines 44-89", "look at the imports". Use even when the user names a shell viewer/lister or says "open the file" — never call host Read, Glob, or any shell file viewer / lister directly. If tilth MCP is unavailable, stop and report rather than fall back. Do NOT use for searching symbols or text (use cheez-search), editing code (use cheez-write), or git/gh operations.
license: MIT
compatibility: Requires tilth MCP server.
allowed-tools: mcp__tilth__tilth_read, mcp__tilth__tilth_list, mcp__tilth__tilth_deps
---

# cheez-read

## Capability detection

Before the first call, verify tilth is reachable. If `mcp__tilth__tilth_read` is absent, install via `tilth install <host>` (see README "Installing tilth MCP").

1. Check that `mcp__tilth__tilth_read` is available. If absent, stop and report `"tilth MCP server is not loaded — cannot proceed."`
2. Make a minimal probe call: `tilth_read(paths: ["README.md#1-1"])`. If the response is a JSON-RPC error or transport failure, stop and report `"tilth MCP server present but unhealthy: <error>"`.
3. Any other failure (file not found, bad section range, etc.) is a **content** issue — proceed normally and report the result.

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

## Scope: when tilth, when not

`tilth_read` owns **source code files in tracked, parseable languages** — anything that may later need symbol navigation, hash anchors, or cheez-write edits. Smart outlining, edit-mode anchors, session deduplication, and `.gitignore`-aware listings all live here.

### Scope and freshness

The tilth MCP server is launched against **one repository** — whatever directory the harness booted it in. There is no persistent index: tilth walks the working tree on demand, parses files with Tree-sitter, and respects `.gitignore`. Practical consequences:

- Always fresh: no index, no rebuild — reads disk on demand.
- Cannot reach files outside that one tree (sibling worktrees, `~/...`, system paths, dependency caches like `node_modules`, `.cargo/registry`, `site-packages`).
- For multi-repo reads, the calling workflow skill must use host `Read` per file directly; tilth is scoped to one tree per MCP session.

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

- **DO NOT use cat / head / tail / less / more / bat** to view code — use `tilth_read`. Hash anchors and outline-vs-full token budgeting only work through tilth.
- **DO NOT use ls / tree / eza / find / fd to enumerate code files** — use `tilth_list`. Token estimates and `.gitignore` filtering only work through tilth.
- **DO NOT use the host Read or Glob tools** on code paths — they bypass tilth's session deduplication and emit no anchors.
- **DO NOT re-read files** shown earlier — reference the prior read.
- **DO NOT use to run code or tests** — use the project's build/test skills.
- **DO NOT use to commit** — use git/gh skills.
- **DO NOT ignore hash anchors** — they are required for edits.

---

## Discipline

Iron Law, Red Flags, and the read Rationalization table live in
[`references/cheez-read-discipline.md`](references/cheez-read-discipline.md).
See [`../../shared/skill-authoring.md`](../../shared/skill-authoring.md) for the template these follow.
