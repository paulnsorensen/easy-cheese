---
name: cheez-write
description: Edit code via hash-anchored tilth MCP edits — replaces sed / awk / perl -i / patch / tee / Edit / Write / shell redirects (`>`, `>>`). Use when the user asks to edit, replace, modify, update, change, delete, or insert code — phrases like "replace this function", "delete lines 44-89", "update validateToken", "add this import", "fix this bug" (when fixing requires editing), or apply a cross-cutting structural change (codemod) like "rewrite every X to Y". Sanctions `sg --rewrite` (ast-grep) for structural codemods that span many files. Always read first via cheez-read to get hash anchors for anchored edits. Prefer surgical anchored edits over whole-file rewrites. If tilth MCP is unavailable, stop and report rather than fall back. Do NOT use for reading files (cheez-read first to get anchors), searching code (use cheez-search), or running tests/builds.
license: MIT
compatibility: Requires tilth MCP server. Optional ast-grep (`sg`) for structural codemods (`sg --rewrite`) that span many files.
allowed-tools: mcp__tilth__tilth_write, mcp__tilth__tilth_read, Bash
---

# cheez-write

> **Hard dependency**: If `mcp__tilth__tilth_write` is unavailable, stop immediately and report
> "tilth MCP server is not loaded — cannot proceed." Do NOT fall back to `Edit`, `Write`,
> or any host tool. Install via `tilth install <host> --edit` — the `--edit` flag is required to expose `tilth_write` (see README "Installing tilth MCP").

## Capability detection

Before the first edit call, verify `mcp__tilth__tilth_write` is in your tool list. If absent, stop: `"tilth MCP server is loaded but edit mode is disabled — re-install with 'tilth install <host> --edit'."` If the first call returns a JSON-RPC transport error (not a hash mismatch), stop: `"tilth MCP server present but unhealthy: <error>"`. Hash mismatches and anchor-not-found are **content** issues — see [Hash Mismatch Handling](#hash-mismatch-handling).

---

## Examples

### "Replace the body of `handleAuth` in `src/auth.ts`"

Step 1 — read the line range to get anchors:

```
tilth_read(paths: ["src/auth.ts#44-89"])
# returns 44:b2c|... and 89:e1d|...
```

Step 2 — apply with the captured anchors:

```json
tilth_write(files: [{
  "path": "src/auth.ts",
  "edits": [{
    "start": "44:b2c",
    "end":   "89:e1d",
    "content": "export function handleAuth(req, res, next) {\n  const token = extractToken(req);\n  if (!validateToken(token)) return res.status(401).end();\n  next();\n}"
  }]
}])
```

Response confirms `Edit applied to src/auth.ts` and may list callers to
review.

### "Hash mismatch — file changed under me"

See [Hash Mismatch Handling](#hash-mismatch-handling) for recovery steps.

---

## Core Principle: Anchors, Not Rewrites

tilth_write uses **hash anchors** — a per-line content fingerprint — to make surgical edits and reject the write if the file changed.

**The protocol:**
1. Read the file section with `tilth_read` (cheez-read) → get hash anchors
2. Note start/end anchors for the block you'll change
3. Call `tilth_write` with those anchors and new content

---

## Scope: when tilth_write, when not

`tilth_write` owns **block edits to tracked source code** — function bodies, signatures, imports, single-line tweaks, multi-edit batches, and cross-file changes. Hash anchors are race-safe; the read-edit protocol is mandatory for any code change that matters.

For everything else, prefer the right tool:

| Change | Use this instead | Why |
|--------|------------------|-----|
| Cross-cutting structural codemod (`JSON.parse(JSON.stringify($X))` → `structuredClone($X)`) across N files | `sg --rewrite` (dry-run-first protocol) | tilth_write needs N reads-for-anchors; codemods template the variable parts |
| Lockfile changes (`Cargo.lock`, `package-lock.json`, `uv.lock`, etc.) | the package manager (`cargo update`, `npm i`, `uv lock`) | Hand-editing lockfiles loses checksum integrity |
| Generated / build artifacts (compiled JS, transpiled output, `*.pb.go`) | regenerate from source | Editing the artifact rots on the next build |
| Brand-new files, no prior content | `tilth_write` (anchor on line 1, end-anchor on the last line for a single-edit insert) | Stay on one path; the anchor cost is negligible for new files |
| Files outside the repo or inside dependency caches (`node_modules`, `.cargo/registry`) | don't edit them | Modifying dependencies is almost always a mistake — fix the source or upstream |
| Binary files, images, PDFs | the producing tool | tilth_write is text-only |

### Routing to LSP rename or Serena

Pre-entry routing decisions — when to prefer LSP rename or Serena symbol-bounded edits over `tilth_write` — are in [`references/routing.md`](references/routing.md).

---

## Hash Anchor Format

When you read a file with tilth_read (a line range, `#symbol`, or heading), lines have anchors:

```
42:a3f|  let x = compute();
43:f1b|  return x;
```

Format: `<line>:<hash>|<content>` (ASCII pipe, no space).

---

## MCP Tool Reference

### tilth_write — Precise File Editing

The minimal shape — single anchor, replacement content:

```json
tilth_write(files: [{
  "path": "src/auth.ts",
  "edits": [
    { "start": "42:a3f", "content": "  let x = recompute();" }
  ]
}])
```

For range replacement, deletion, multi-edit, insert-after, cross-file
batches, and the `diff: true` response option, see
[`references/edit-patterns.md`](references/edit-patterns.md).

---

## Hash Mismatch Handling

If the file changed since you read it:

```
Error: Hash mismatch at line 44
Expected: b2c
Found: f9a

Current content:
44:f9a|export async function handleAuth(req, res, next) {
...
```

**Recovery:**
1. Read the section again → get new anchors.
2. Review the current content (someone else may have made changes).
3. Edit with new anchors.

### Repeated mismatches → bail out, don't loop

If you hit **two consecutive mismatches** on the same anchor, you're racing a
concurrent writer. `tilth_write` has no fuzzy / search-replace mode — there
is no "ignore the hash, just match this string" option. A third retry will
likely lose the same race.

The correct move is to bail and report:

1. Read the latest section one final time and capture the current content.
2. Prepare the new content as a unified diff or full block, but **do not
   apply** it.
3. Report `"hash-anchor race on <path>:<line>; current content and proposed
   replacement attached. Retry once the file is quiescent or apply manually."`
   along with the captured anchors and proposed content.
4. Stop. Let the orchestrator (or a human) decide whether to apply the change
   or escalate.

---

## Caller Updates After Signature Changes

When you change a signature, `tilth_write` surfaces callers that may need updating — see [edit-patterns.md#caller-update-notices](references/edit-patterns.md#caller-update-notices).

---

## Common Patterns

| Goal | Reference |
|------|-----------|
| Replace one line | [edit-patterns.md#single-line-replacement](references/edit-patterns.md#single-line-replacement) |
| Replace a range | [edit-patterns.md#multi-line-range-replacement](references/edit-patterns.md#multi-line-range-replacement) |
| Delete a block | [edit-patterns.md#delete-a-block](references/edit-patterns.md#delete-a-block) |
| Insert after a line | [edit-patterns.md#insert-after-a-line](references/edit-patterns.md#insert-after-a-line) |
| Multi-edit in one file | [edit-patterns.md#multiple-edits-in-one-call](references/edit-patterns.md#multiple-edits-in-one-call) |
| Cross-file change | [edit-patterns.md#edits-across-multiple-files](references/edit-patterns.md#edits-across-multiple-files) |

---

## When full-file rewrite is acceptable

Hash-anchored, surgical edits are the default. There is one exception:

| File size | Policy |
|-----------|--------|
| **> 150 lines** | Never rewrite the whole file. Always hash-anchored. |
| **≤ 150 lines** | Anchored single-edit preferred, but a full rewrite (delete-everything + insert) is acceptable when **≥ 80%** of the file is changing. Below that threshold, do the surgical edit. |

The 150-line / 80% threshold follows 2026 data (Cursor, can.ac, the Morph benchmark): full rewrites tie or beat diff-style on small files, while large files always stay anchored.

When you do rewrite a small file in full, still use `tilth_write` (anchor on
line 1, end-anchor on the last line). Do **not** drop to host `Write` —
that bypasses tilth's hash-mismatch safety.

---

## Structural codemods — `sg --rewrite` escape

`tilth_write` edits known blocks, one read-for-anchors per location. For cross-cutting structural codemods where the surrounding text varies — "rewrite every `JSON.parse(JSON.stringify($X))` to `structuredClone($X)`" — drop to `sg --rewrite` (ast-grep) via Bash, which templates the variable parts via metavars and is the **only** sanctioned shell escape from cheez-write. It has no hash-anchor safety: run each codemod as one transactional change between two clean git states. For metavar syntax and the non-negotiable dry-run-first protocol, see [`../cheez-search/references/sg-patterns.md`](../cheez-search/references/sg-patterns.md).

---

## DO NOT

- **DO NOT guess hash values** — always read first to get current anchors.
- **DO NOT ignore hash mismatches** — re-read and retry (see Hash Mismatch Handling).
- **DO NOT use sed / awk / perl -i** to edit code — they bypass hash anchors and structural safety, and have no mismatch detection. `sg --rewrite` is the *only* sanctioned shell escape, and only for structural codemods that follow the dry-run-first protocol.
- **DO NOT use `patch`** to apply diffs to code — `tilth_write`'s anchored ranges are the safe equivalent.
- **DO NOT use `tee` or shell redirects (`>`, `>>`)** to overwrite/append code files — both bypass anchors. Use `tilth_write`.
- **DO NOT use the host Edit/Write tool** — use `tilth_write` (or `sg --rewrite` for structural codemods) exclusively for code.
- **DO NOT use `sg --rewrite` for one-off block edits** — that's `tilth_write` territory. The codemod escape is only for cross-cutting structural changes; using it on a single location wastes its strength and skips hash-anchor safety.
- **DO NOT skip the dry-run-first protocol for `sg --rewrite`** — search-only first, clean working tree, then `-U`. Never combine search+rewrite blindly.
- **DO NOT edit without reading** — you need the anchors.
- **DO NOT run tests, commit, or review from this skill** — use the project's test/build, git/gh, and `/age` skills.
- **DO NOT run tests, commit, or review from this skill** — use the project's test/build, git/gh, and `/age` skills.
