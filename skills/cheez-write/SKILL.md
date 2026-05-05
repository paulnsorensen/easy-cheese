---
name: cheez-write
description: This skill should be used when the user asks to edit, replace, modify, update, change, delete, or insert code in a file — phrases like "replace this function", "delete lines 44-89", "update validateToken", "change the implementation", "add this import", "fix this bug" (when fixing requires editing). Replaces sed / awk / Edit / Write with hash-anchored tilth MCP edits. Always read first via cheez-read to get hash anchors. Never rewrite whole files. If tilth MCP is unavailable, stop and report rather than fall back.
license: MIT
compatibility: Requires tilth MCP server.
allowed-tools: mcp__tilth__tilth_edit mcp__tilth__tilth_read
---

# cheez-write

> **Hard dependency**: If `mcp__tilth__tilth_edit` is unavailable, stop immediately and report
> "tilth MCP server is not loaded — cannot proceed." Do NOT fall back to `Edit`, `Write`,
> or any host tool.

Hash-anchored file editing via **tilth MCP** (`tilth_edit`).
Never rewrite whole files. Use hash anchors from tilth_read to make precise, surgical edits.

---

## Core Principle: Anchors, Not Rewrites

Traditional AI editing rewrites entire files, wasting tokens and risking data loss.
tilth_edit uses **hash anchors** — unique identifiers for each line — to:
- Make precise, surgical changes
- Reject edits if the file changed (hash mismatch)
- Show you exactly what changed

**The protocol:**
1. Read the file section with `tilth_read` (cheez-read) → get hash anchors
2. Note start/end anchors for the block you'll change
3. Call `tilth_edit` with those anchors and new content

---

## Hash Anchor Format

When you read a file with tilth_read, lines have anchors:

```
42:a3f│  let x = compute();
43:f1b│  return x;
```

Format: `<line>:<hash>│ <content>`

The hash is a short content fingerprint. If someone else edits the file,
hashes change, and your edit is safely rejected.

---

## MCP Tool Reference

### tilth_edit — Precise File Editing

**Single line edit:**
```json
tilth_edit({
  "path": "src/auth.ts",
  "edits": [
    { "start": "42:a3f", "content": "  let x = recompute();" }
  ]
})
```

**Multi-line range replacement:**
```json
tilth_edit({
  "path": "src/auth.ts",
  "edits": [
    {
      "start": "44:b2c",
      "end": "89:e1d",
      "content": "export function handleAuth(req, res, next) {\n  // new implementation\n  const token = extractToken(req);\n  if (!token) return res.status(401).end();\n  next();\n}"
    }
  ]
})
```

**Delete a block:**
```json
tilth_edit({
  "path": "src/auth.ts",
  "edits": [
    { "start": "44:b2c", "end": "89:e1d", "content": "" }
  ]
})
```

**Multiple edits in one call:**
```json
tilth_edit({
  "path": "src/auth.ts",
  "edits": [
    { "start": "12:a1b", "content": "import { newHelper } from './helpers';" },
    { "start": "44:b2c", "end": "89:e1d", "content": "// replaced function\n..." }
  ]
})
```

**Show diff in response:**
```json
tilth_edit({
  "path": "src/auth.ts",
  "diff": true,
  "edits": [...]
})
```

---

## The Read-Edit Protocol

### Step 1: Read to Get Anchors

```
tilth_read(path: "src/auth.ts", section: "44-89")
```

Output:
```
44:b2c│ export function handleAuth(req, res, next) {
45:c3d│   const token = req.headers.authorization?.split(' ')[1];
...
88:d4e│   next();
89:e1d│ }
```

### Step 2: Note Your Anchors

- **Start anchor:** `44:b2c` (first line of function)
- **End anchor:** `89:e1d` (closing brace)

### Step 3: Edit with Anchors

```json
tilth_edit({
  "path": "src/auth.ts",
  "edits": [{
    "start": "44:b2c",
    "end": "89:e1d",
    "content": "export function handleAuth(req, res, next) {\n  const token = extractToken(req);\n  if (!validateToken(token)) {\n    return res.status(401).json({ error: 'Invalid token' });\n  }\n  req.user = decodeToken(token);\n  next();\n}"
  }]
})
```

---

## Replacing Entire Functions

This is the most common use case. The pattern:

1. **Read the function** (outline first if file is large):
   ```
   tilth_read(path: "src/auth.ts")
   # See: [44-89]  export fn handleAuth(req, res, next)

   tilth_read(path: "src/auth.ts", section: "44-89")
   # Get hash anchors
   ```

2. **Note start/end anchors** from the hashlined output.

3. **Replace the entire function body:**
   ```json
   tilth_edit({
     "path": "src/auth.ts",
     "edits": [{
       "start": "44:b2c",
       "end": "89:e1d",
       "content": "<your new function implementation>"
     }]
   })
   ```

---

## Hash Mismatch Handling

If the file changed since you read it:

```
Error: Hash mismatch at line 44
Expected: b2c
Found: f9a

Current content:
44:f9a│ export async function handleAuth(req, res, next) {
...
```

**Recovery:**
1. Read the section again → get new anchors.
2. Review the current content (someone else may have made changes).
3. Edit with new anchors.

This is a **safety feature**, not a bug.

---

## Caller Updates After Signature Changes

When you edit a function signature, tilth_edit shows callers that may need updating:

```
Edit applied to src/auth.ts

── callers that may need updates ──
  src/routes/api.ts:34   router.use('/api/*', handleAuth)
  src/routes/admin.ts:12 app.use(handleAuth)
  src/middleware.ts:8    const wrapped = handleAuth(...)
```

Check these locations and update if needed.

---

## Common Patterns

### Insert After a Line

Use the start anchor of the line AFTER where you want to insert:

```json
tilth_edit({
  "path": "src/auth.ts",
  "edits": [{
    "start": "13:abc",
    "content": "import { newHelper } from './helpers';\nimport { oldImport } from './old';"
  }]
})
```

This replaces line 13. To truly "insert", include the original line 13 content
in your new content.

### Delete Multiple Functions

```json
tilth_edit({
  "path": "src/auth.ts",
  "edits": [
    { "start": "44:b2c", "end": "89:e1d", "content": "" },
    { "start": "120:f4g", "end": "180:h5i", "content": "" }
  ]
})
```

### Batch Edits Across Files

Make separate tilth_edit calls per file (cannot batch across files):

```
tilth_edit({ path: "src/auth.ts", edits: [...] })
tilth_edit({ path: "src/routes.ts", edits: [...] })
```

---

## Large Files: Outline First

For large files, tilth_read shows an outline, not hashlined content:

```
# src/giant.ts (2400 lines, ~32k tokens) [outline]

[1-20]    imports
[22-89]   interface Config
[91-450]  class GiantHandler
  [100-180]  fn process
  [182-340]  fn validate
```

**To edit, drill into the specific section:**

```
tilth_read(path: "src/giant.ts", section: "100-180")
# Now you get hashlined content for fn process
```

Then edit with those anchors.

---

## DO NOT

- **DO NOT rewrite entire files** — use hash anchors for surgical edits.
- **DO NOT guess hash values** — always read first to get current anchors.
- **DO NOT ignore hash mismatches** — re-read and retry.
- **DO NOT use host Edit/Write tool** — use tilth_edit exclusively.
- **DO NOT edit without reading** — you need the anchors.
- **DO NOT use for reading** — use cheez-read.
- **DO NOT use for searching** — use cheez-search.

---

## What This Skill Doesn't Do

- **Read files** — use cheez-read first to get anchors.
- **Search code** — use cheez-search to find what to edit.
- **Run tests after editing** — use test/build skills.
- **Commit changes** — use git/gh skills.
- **Review your edits** — use age/code-review skills.
