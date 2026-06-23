---
name: cheez-read
description: Read and list files via AST-aware tilth MCP — replaces cat / head / tail / less / more / bat / ls / tree / eza / find / fd / Read / Glob. Use when the user asks to read, view, show, open, or display a file or directory — phrases like "read src/auth.ts", "show me this file", "what's in this directory", "view lines 44-89", "look at the imports". Use even when the user says "cat", "less", "bat", "tree", "ls", "find", "fd", or "open the file" — never call host Read, Glob, or any shell file viewer / lister directly. If tilth MCP is unavailable, stop and report rather than fall back. Do NOT use for searching symbols or text (use cheez-search), editing code (use cheez-write), or git/gh operations.
license: MIT
compatibility: Requires tilth MCP server.
allowed-tools: mcp__tilth__tilth_read, mcp__tilth__tilth_list, mcp__tilth__tilth_deps
---

# cheez-read

> **Hard dependency**: If `mcp__tilth__tilth_read` is unavailable, stop immediately and report
> "tilth MCP server is not loaded — cannot proceed." Do NOT fall back to `cat`, `Read`, `Glob`,
> or any host tool. Install via `tilth install <host>` (see README "Installing tilth MCP").

## Capability detection

Before the first call, verify tilth is reachable:

1. Check that `mcp__tilth__tilth_read` is available. If absent, stop and report `"tilth MCP server is not loaded — cannot proceed."`
2. Make a minimal probe call: `tilth_read(paths: ["README.md#1-1"])`. If the response is a JSON-RPC error or transport failure, stop and report `"tilth MCP server present but unhealthy: <error>"`.
3. Any other failure (file not found, bad section range, etc.) is a **content** issue — proceed normally and report the result.

Smart code reading via **tilth MCP** (`tilth_read`, `tilth_list`, `tilth_deps`).
tilth replaces cat/head/tail with AST-aware file reading that understands code structure.

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
tilth_list(glob: "*.ts", scope: "src/handlers/")
```

```text
src/handlers/auth.ts      (~1.8k tokens)
src/handlers/orders.ts    (~3.1k tokens)
src/handlers/webhooks.ts  (~620 tokens)
```

Token estimates inform what to read in full vs outline before spending
any context on it.

---

## Core Principle: Read Smart, Not More

tilth decides what to show based on file size and structure:
- **Small files** → full content with line numbers
- **Large files** → structural outline with line ranges
- **Binary/generated** → skipped with type indicator

This avoids wasting tokens on a giant lockfile or minified bundle.

---

## Scope: when tilth, when not

`tilth_read` owns **source code files in tracked, parseable languages** — anything that may later need symbol navigation, hash anchors, or cheez-write edits. Smart outlining, edit-mode anchors, session deduplication, and `.gitignore`-aware listings all live here.

### Scope and freshness

The tilth MCP server is launched against **one repository** — whatever directory the harness booted it in. There is no persistent index: tilth walks the working tree on demand, parses files with Tree-sitter, and respects `.gitignore`. Practical consequences:

- No startup wait, no rebuild step, no staleness — the latest content on disk is what tilth reads.
- Cannot reach files outside that one tree (sibling worktrees, `~/...`, system paths, dependency caches like `node_modules`, `.cargo/registry`, `site-packages`).
- For multi-repo reads, the calling workflow skill must use host `Read` per file directly, or use code-review-graph's cross-repo tools — see cheez-search's [When code-review-graph beats tilth](../cheez-search/SKILL.md#when-code-review-graph-beats-tilth-if-your-harness-has-it) section.

### When NOT to invoke `/cheez-read`

Inside `/cheez-read`, the contract is hard: tilth-only, no host fallback. The reads below are **out of scope** for the skill — don't enter cheez-read for them in the first place. They're listed here so workflow skills know where to route instead, consistent with the README rule "anything that touches source code goes through `cheez-*`; everything else stays on host tools".

| File (don't use cheez-read) | Route to | Why |
|-----------------------------|----------|-----|
| Binary content (images, PDFs) | host `Read` (multimodal) from the calling workflow skill | tilth can't render these |
| Streaming output, process logs, huge CSVs | host `Bash` with `head`/`tail`, `awk`, `jq` from the calling workflow skill | Format-specific tools beat outline mode here |
| Lockfiles, minified bundles, generated artifacts | don't read by hand — regenerate from source | tilth deliberately skips these |
| Files outside the repo (system paths, sibling worktrees, `~/...`) | host `Read` from the calling workflow skill | tilth is repo-scoped (see above) |
| Dependency source (`node_modules`, `.cargo/registry`, `site-packages`, vendor caches) | LSP `textDocument/definition` from the calling workflow skill if a server is reachable; otherwise don't read by hand | Reading dependency source by hand is almost always wrong; the LSP resolves the right module version |

If the file is code in this repo, **always cheez-read** — the hash anchors are non-negotiable for safe edits later, and the tilth-only contract holds inside the skill.

### When LSP beats tilth for navigation (if the harness has one)

**easy-cheese does not install LSP** — it is whatever language servers the harness already exposes. When an LSP is reachable for the file's language and the navigation question is type-grounded, prefer the LSP method:

| Goal | LSP method (when available) | Why LSP wins |
|------|------------------------------|--------------|
| Jump to where a symbol is *defined*, following imports / re-exports | `textDocument/definition` | Resolves the actual import graph; tilth surfaces every textual definition with that name |
| Read the *resolved* type / generic instantiation at a call site | `textDocument/hover` | Returns the typechecker's view of the symbol, not just the source declaration |
| Open the file declaring the *type* of a value | `textDocument/typeDefinition` | Walks through type aliases and generic parameters |
| Browse symbols across the whole project, semantically ranked | `workspace/symbol` | LSP indexes the project's type graph; tilth indexes the tree |

If no LSP is installed for the language, or the file is in a broken / incomplete state where the server cannot resolve, stay on tilth. tilth still wins on outline reading, hash-anchored prep for edits, polyglot directory listings, and any read where a `.gitignore`-aware token estimate is required.

### When Serena beats tilth for symbol-table reads (if your harness has it)

[Serena](https://github.com/oraios/serena) is an LSP-driven MCP. When Serena is configured for the codebase (`.serena/project.yml` present) and the read is symbol-shaped, the **calling workflow skill** should route directly to Serena rather than entering `/cheez-read`:

| Goal | Serena tool | Why |
|------|-------------|-----|
| Just the symbol table of one file (no source lines) | `mcp__serena__get_symbols_overview` | Cheaper than tilth outline mode — LSP-indexed, no parse pass |
| Read a single symbol's body by name (no line range needed) | `mcp__serena__find_symbol` with body inclusion | Skips the "outline → drill into 44-89" round-trip |

`/cheez-read` itself stays tilth-only — its `allowed-tools` frontmatter does not include `mcp__serena__*` and shouldn't. The routing decision happens in the workflow skill *before* it enters `/cheez-read`. Enter `/cheez-read` when you need hash anchors (any edit follows up), a `tilth_list` directory listing with token estimates, token-budgeted preview mode, or when Serena is unavailable. Serena gives you the symbol; tilth gives you the anchor — if you're going to edit afterwards, prefer tilth so the anchor is already in hand. See [`cheez-write`](../cheez-write/SKILL.md) for the symmetric "When Serena beats `tilth_write`" guidance.

---

## MCP Tool Reference

### tilth_read — Smart File Reading

```
tilth_read(paths: ["src/auth.ts"])
```

**Output for small files:**
```
# src/auth.ts (258 lines, ~3.4k tokens) [full]

1 │ import express from 'express';
2 │ import jwt from 'jsonwebtoken';
...
```

**Output for large files (automatic outline):**
```
# src/auth.ts (1240 lines, ~16k tokens) [outline]

[1-12]   imports: express(2), jsonwebtoken, @/config
[14-22]  interface AuthConfig
[24-42]  fn validateToken(token: string): Claims | null
[44-89]  export fn handleAuth(req, res, next)
[91-258] export class AuthManager
  [99-130]  fn authenticate(credentials)
  [132-180] fn authorize(user, resource)
```

**Drilling into sections:**
```
# Line range
tilth_read(paths: ["src/auth.ts#44-89"])

# Markdown heading
tilth_read(paths: ["docs/guide.md### Installation"])
```

**Multiple files in one call:**
```
tilth_read(paths: ["src/auth.ts", "src/routes.ts", "src/middleware.ts"])
```

---

## Hash Anchors — The Edit Bridge

When reading files in **edit mode**, tilth outputs **hash-anchored lines**:

```
42:a3f|  let x = compute();
43:f1b|  return x;
```

The format is `<line>:<hash>|<content>`.

> Plain reads use a `│` (U+2502) column separator. **Edit-mode reads** (the
> ones required for cheez-write) use `:<hash>|` — note the ASCII pipe and
> the colon. Anchors are only emitted when tilth is run in `--edit` mode.

**Why this matters:**
- These hashes uniquely identify the line content
- They're used by `tilth_write` (cheez-write) for precise edits
- If the file changes, hashes won't match → edit is rejected safely
- Reading before editing is mandatory to get current hashes

**Memorize anchors for functions to edit:**
- Note the start hash of function definitions
- Note the end hash for multi-line replacements
- Pass these to cheez-write later

---

## tilth_list — Directory Listing

Replaces `ls`, `find`, `pwd`, and the Glob tool.

```
tilth_list(glob: "**/*.ts", scope: "src/")
```

**Output:**
```
src/auth.ts  (~3.4k tokens)
src/routes.ts  (~2.1k tokens)
src/middleware.ts  (~1.8k tokens)
```

Token estimates inform what to read in full vs outline.

**Common patterns:**
```
# All TypeScript files
tilth_list(glob: "**/*.ts")

# Test files only
tilth_list(glob: "**/*.test.ts")

# Specific directory
tilth_list(glob: "*", scope: "src/handlers/")

# Exclude patterns (negation in the same glob)
tilth_list(glob: "!*_test.go", scope: ".")
```

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

## Session Memory (Deduplication)

tilth tracks reads within the current session:
- Re-reading the same section shows `[shown earlier]` instead of full content
- This saves significant tokens over long sessions
- Forces reuse of memorized anchors instead of re-reading

**Implication:** Read once, memorize anchors, reference later.

---

## Reading Protocol

### For Understanding Code

1. **Start with outline** (let tilth auto-decide):
   ```
   tilth_read(paths: ["src/auth.ts"])
   ```

2. **Drill into relevant sections:**
   ```
   tilth_read(paths: ["src/auth.ts#44-89"])
   ```

3. **Check dependencies if needed:**
   ```
   tilth_deps(path: "src/auth.ts")
   ```

### For Preparing Edits

1. **Read the target section to get hash anchors:**
   ```
   tilth_read(paths: ["src/auth.ts#44-89"])
   ```

2. **Memorize:**
   - Start anchor: `44:a3f`
   - End anchor: `89:b7c`

3. **Pass these to cheez-write** (`tilth_write`) for the edit.

### For Exploring a Directory

1. **List files with token estimates:**
   ```
   tilth_list(glob: "*", scope: "src/handlers/")
   ```

2. **Read small files fully, outline large ones:**
   ```
   tilth_read(paths: ["small.ts", "large.ts"])
   ```

---

## DO NOT

- **DO NOT use cat / head / tail / less / more / bat** to view code — use `tilth_read`. Hash anchors and outline-vs-full token budgeting only work through tilth.
- **DO NOT use ls / tree / eza / find / fd to enumerate code files** — use `tilth_list`. Token estimates and `.gitignore` filtering only work through tilth.
- **DO NOT use the host Read or Glob tools** on code paths — they bypass tilth's session deduplication and emit no anchors.
- **DO NOT re-read files** shown earlier — reference the prior read.
- **DO NOT use for searching** — use cheez-search.
- **DO NOT use for editing** — use cheez-write.
- **DO NOT ignore hash anchors** — they are required for edits.

---

## Output Token Budget

tilth uses ~6000 tokens as the outline threshold. Files under this show in full;
files over this get structural outlines. Use the `#n-m` line suffix (e.g. `paths: ["src/auth.ts#44-89"]`) or the `#symbol_name` suffix (e.g. `paths: ["src/auth.ts#handleAuth"]`) to get hash-anchored content for specific ranges or symbols. Use `mode:stripped` for a full-file plain-comment-stripped outline read when you need to survey a large file without hash anchors.

---

## What This Skill Doesn't Do

- **Search for symbols or text** — use cheez-search.
- **Edit files** — use cheez-write.
- **Run code or tests** — use appropriate build/test skills.
- **Commit changes** — use git/gh skills.
