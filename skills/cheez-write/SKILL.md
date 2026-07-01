---
name: cheez-write
description: Edit code through an anchored, stale-safe backend — tilth MCP by default, or harness-native anchored edits/LSP refactors when they reject stale snapshots. Replaces sed / awk / perl -i / patch / tee / Edit / Write / shell redirects (`>`, `>>`). Use when the user asks to edit, replace, modify, update, change, delete, or insert code — phrases like "replace this function", "delete lines 44-89", "update validateToken", "add this import", "fix this bug" (when fixing requires editing), or apply a cross-cutting structural change (codemod) like "rewrite every X to Y". Sanctions `sg --rewrite` for structural codemods that span many files. Always read first via cheez-read to get anchors for anchored edits. If no anchored edit backend is available, stop and report rather than falling back to plain text rewrites. Do NOT use for reading files (cheez-read first), searching code (use cheez-search), or running tests/builds.
license: MIT
compatibility: Prefers tilth MCP with edit mode. Harness-native anchored edits and LSP rename/code actions are acceptable when they reject stale snapshots. Optional ast-grep (`sg`) for structural codemods (`sg --rewrite`) that span many files.
allowed-tools: mcp__tilth__tilth_write, mcp__tilth__tilth_read, Bash, Edit, AST Grep, LSP
---

# cheez-write

> **Backend contract**: use an anchored edit backend that rejects stale snapshots. Prefer `mcp__tilth__tilth_write`; a harness-native Edit tool, LSP rename/code action, or equivalent backend is acceptable only when it carries line/snapshot anchors and refuses to apply after the file changes. Plain shell rewrites are never acceptable.

## Backend detection

Before the first edit call, choose the strongest safe backend:

1. If `mcp__tilth__tilth_write` is in your tool list, use it. If it is absent but other tilth tools are present, stop with `"tilth MCP server is loaded but edit mode is disabled — re-install with 'tilth install <host> --edit'."` unless the harness has an equivalent anchored edit backend.
2. If the harness exposes anchored Edit/Write operations or LSP rename/code actions that reject stale snapshots, those satisfy the backend contract.
3. If only unanchored text rewriting is available (`sed`, `awk`, `perl -i`, `patch`, shell redirects, blind host writes), stop and report `"no anchored code edit backend is available — cannot proceed."`

Hash mismatches and anchor-not-found are **content** issues — see [Hash Mismatch Handling](#hash-mismatch-handling).

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

The edit backend must identify the current file state — tilth hash anchors, harness snapshot tags, or LSP workspace edits — and reject the write if the file changed.

**The protocol:**
1. Read the file section with cheez-read → get current anchors or snapshot ids
2. Note start/end anchors for the block you'll change
3. Apply the edit through the anchored backend

---

## Scope: when to use anchored edits, when not

`cheez-write` owns **block edits to tracked source code** — function bodies, signatures, imports, single-line tweaks, multi-edit batches, and cross-file changes. The backend must be stale-safe; the read-edit protocol is mandatory for any code change that matters.

For everything else, prefer the right tool:

| Change | Use this instead | Why |
|--------|------------------|-----|
| Cross-cutting structural codemod (`JSON.parse(JSON.stringify($X))` → `structuredClone($X)`) across N files | `sg --rewrite` (dry-run-first protocol) | Codemods template the variable parts; anchored edits are better for known blocks |
| Semantic rename or server-known refactor | LSP rename/code action | LSP follows scope, overloads, re-exports, and imports |
| Lockfile changes (`Cargo.lock`, `package-lock.json`, `uv.lock`, etc.) | the package manager (`cargo update`, `npm i`, `uv lock`) | Hand-editing lockfiles loses checksum integrity |
| Generated / build artifacts (compiled JS, transpiled output, `*.pb.go`) | regenerate from source | Editing the artifact rots on the next build |
| Brand-new files, no prior content | anchored create/write backend | Stay stale-safe even when creating files |
| Files outside the repo or inside dependency caches (`node_modules`, `.cargo/registry`) | don't edit them | Modifying dependencies is almost always a mistake — fix the source or upstream |
| Binary files, images, PDFs | the producing tool | code edit backends are text-only |

---

## Anchor Format

Use whatever anchor format the selected backend emits:

- tilth: `<line>:<hash>|<content>`; pass `<line>:<hash>` into `tilth_write`.
- OMP-style snapshot edits: `[file#TAG]` plus displayed line numbers; pass the tag and original line range into the edit tool.
- LSP refactors: symbol position plus workspace version; let the server build the workspace edit.

Do not translate between anchor systems. Read with the same backend family that will write.

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

When changing a signature, use LSP references or the edit backend's caller notices before finishing. Missed callsites are bugs.

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

Anchored, surgical edits are the default. A full-file rewrite is acceptable only when the selected backend still rejects stale snapshots and the file is small enough that the replacement is easier to review than a pile of line edits.

| File size | Policy |
|-----------|--------|
| **> 150 lines** | Never rewrite the whole file. Always use anchored block edits. |
| **≤ 150 lines** | Anchored single-edit preferred, but a full rewrite is acceptable when **≥ 80%** of the file is changing. Below that threshold, do the surgical edit. |

The 150-line / 80% threshold follows 2026 data (Cursor, can.ac, the Morph benchmark): full rewrites tie or beat diff-style on small files, while large files always stay anchored.

Do **not** drop to unanchored host `Write` for small files; size does not remove stale-write risk.

---

## Structural codemods — `sg --rewrite` escape

Anchored edits own known blocks, one read-for-anchors per location. For cross-cutting structural codemods where the surrounding text varies — "rewrite every `JSON.parse(JSON.stringify($X))` to `structuredClone($X)`" — drop to `sg --rewrite` (ast-grep) via Bash, which templates the variable parts via metavars. It has no hash-anchor safety: run each codemod as one transactional change between two clean git states. For metavar syntax and the non-negotiable dry-run-first protocol, see [`../cheez-search/references/sg-patterns.md`](../cheez-search/references/sg-patterns.md).

---

## DO NOT

- **DO NOT guess anchors** — always read first to get current anchors or snapshot ids.
- **DO NOT ignore stale-anchor failures** — re-read and retry (see Hash Mismatch Handling).
- **DO NOT use sed / awk / perl -i** to edit code — they bypass anchors and structural safety, and have no mismatch detection. `sg --rewrite` is the only sanctioned shell escape, and only for structural codemods that follow the dry-run-first protocol.
- **DO NOT use `patch`** to apply diffs to code — anchored range edits are the safe equivalent.
- **DO NOT use `tee` or shell redirects (`>`, `>>`)** to overwrite/append code files — both bypass anchors. Use an anchored edit backend.
- **DO NOT use unanchored host Edit/Write tools** — use tilth_write, harness-native anchored edits, or LSP workspace edits.
- **DO NOT use `sg --rewrite` for one-off block edits** — use an anchored edit. The codemod escape is only for cross-cutting structural changes.
- **DO NOT skip the dry-run-first protocol for `sg --rewrite`** — search-only first, clean working tree, then `-U`. Never combine search+rewrite blindly.
- **DO NOT edit without reading** — anchors come from the read step.
- **DO NOT run tests, commit, or review from this skill** — use the project's test/build, git/gh, and `/age` skills.
- **DO NOT use for reading or searching** — read with `/cheez-read`, search with `/cheez-search`.
