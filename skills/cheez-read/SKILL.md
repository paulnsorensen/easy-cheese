---
name: cheez-read
description: This skill should be used when the user asks to read, view, show, open, or display the contents of a file or directory — phrases like "read src/auth.ts", "show me this file", "what's in this directory", "view lines 44-89", "look at the imports". Replaces cat / head / tail / ls / find / Read / Glob with AST-aware tilth MCP reading. Use even when the user says "cat" or "open the file" — never call host Read or Glob directly. If tilth MCP is unavailable, stop and report rather than fall back.
license: MIT
compatibility: Requires tilth MCP server.
allowed-tools: mcp__tilth__tilth_read mcp__tilth__tilth_files mcp__tilth__tilth_deps
---

# cheez-read

> **Hard dependency**: If `mcp__tilth__tilth_read` is unavailable, stop immediately and report
> "tilth MCP server is not loaded — cannot proceed." Do NOT fall back to `cat`, `Read`, `Glob`,
> or any host tool.

Smart code reading via **tilth MCP** (`tilth_read`, `tilth_files`, `tilth_deps`).
tilth replaces cat/head/tail with AST-aware file reading that understands code structure.

---

## Core Principle: Read Smart, Not More

tilth decides what to show based on file size and structure:
- **Small files** → full content with line numbers
- **Large files** → structural outline with line ranges
- **Binary/generated** → skipped with type indicator

This means you never waste tokens on a giant lockfile or minified bundle.

---

## MCP Tool Reference

### tilth_read — Smart File Reading

```
tilth_read(path: "src/auth.ts")
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
tilth_read(path: "src/auth.ts", section: "44-89")

# Markdown heading
tilth_read(path: "docs/guide.md", section: "## Installation")
```

**Multiple files in one call:**
```
tilth_read(paths: ["src/auth.ts", "src/routes.ts", "src/middleware.ts"])
```

---

## Hash Anchors — The Edit Bridge

When reading files, tilth outputs **hash-anchored lines**:

```
42:a3f│  let x = compute();
43:f1b│  return x;
```

The format is `<line>:<hash>│ <content>`.

**Why this matters:**
- These hashes uniquely identify the line content
- They're used by `tilth_edit` (cheez-write) for precise edits
- If the file changes, hashes won't match → edit is rejected safely
- You MUST read before editing to get current hashes

**Memorize anchors for functions you'll edit:**
- Note the start hash of function definitions
- Note the end hash for multi-line replacements
- Pass these to cheez-write later

---

## tilth_files — Directory Listing

Replaces `ls`, `find`, `pwd`, and the Glob tool.

```
tilth_files(glob: "**/*.ts", scope: "src/")
```

**Output:**
```
src/auth.ts  (~3.4k tokens)
src/routes.ts  (~2.1k tokens)
src/middleware.ts  (~1.8k tokens)
```

Token estimates help you decide what to read in full vs outline.

**Common patterns:**
```
# All TypeScript files
tilth_files(glob: "**/*.ts")

# Test files only
tilth_files(glob: "**/*.test.ts")

# Specific directory
tilth_files(glob: "*", scope: "src/handlers/")

# Exclude patterns
tilth_files(glob: "**/*.go", scope: ".", exclude: "*_test.go")
```

---

## tilth_deps — Blast Radius Check

Shows what imports this file and what it imports.

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

**Use ONLY before:**
- Renaming a file or module
- Removing exports
- Changing a function's signature
- Understanding refactoring impact

---

## Session Memory (Deduplication)

tilth tracks what you've read in the current session:
- Re-reading the same section shows `[shown earlier]` instead of full content
- This saves significant tokens over long sessions
- Forces you to reference memorized anchors instead of re-reading

**Implication:** Read once, memorize anchors, reference later.

---

## Reading Protocol

### For Understanding Code

1. **Start with outline** (let tilth auto-decide):
   ```
   tilth_read(path: "src/auth.ts")
   ```

2. **Drill into relevant sections:**
   ```
   tilth_read(path: "src/auth.ts", section: "44-89")
   ```

3. **Check dependencies if needed:**
   ```
   tilth_deps(path: "src/auth.ts")
   ```

### For Preparing Edits

1. **Read the target section to get hash anchors:**
   ```
   tilth_read(path: "src/auth.ts", section: "44-89")
   ```

2. **Memorize:**
   - Start anchor: `44:a3f`
   - End anchor: `89:b7c`

3. **Pass these to cheez-write** (tilth_edit) for the edit.

### For Exploring a Directory

1. **List files with token estimates:**
   ```
   tilth_files(glob: "*", scope: "src/handlers/")
   ```

2. **Read small files fully, outline large ones:**
   ```
   tilth_read(paths: ["small.ts", "large.ts"])
   ```

---

## DO NOT

- **DO NOT use cat/head/tail** — use tilth_read.
- **DO NOT use ls/find** — use tilth_files.
- **DO NOT re-read files** shown earlier — reference your notes.
- **DO NOT use for searching** — use cheez-search.
- **DO NOT use for editing** — use cheez-write.
- **DO NOT ignore hash anchors** — you'll need them for edits.

---

## Output Token Budget

tilth uses ~6000 tokens as the outline threshold. Files under this show in full;
files over this get structural outlines. Use `section` to get hashlined content
for specific ranges when preparing edits on large files.

---

## What This Skill Doesn't Do

- **Search for symbols or text** — use cheez-search.
- **Edit files** — use cheez-write.
- **Run code or tests** — use appropriate build/test skills.
- **Commit changes** — use git/gh skills.
