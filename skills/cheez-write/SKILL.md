---
name: cheez-write
description: Edit code through the safest stale-checking backend — prefer code-intelligence backends (tilth MCP tag-anchored edits, LSP workspace edits, `sg --rewrite` for structural codemods); fall back to native anchored edits only when no code-intel backend matches. Use when the user asks to edit, replace, modify, update, change, delete, or insert code — phrases like "replace this function", "delete lines 44-89", "update validateToken", "add this import", "fix this bug" (when fixing requires editing), or apply a cross-cutting codemod like "rewrite every X to Y". Do NOT use for reading files (use cheez-read), searching code (use cheez-search), or running tests/builds.
license: MIT
compatibility: Prefers code-intelligence backends — tilth MCP edit mode, LSP workspace edits, AST rewrites. Harness-native anchored edits are acceptable fallbacks when they match the requested edit shape and reject or bound stale writes.
---

# cheez-write

> **Backend contract**: use a stale-safe edit backend. The backend must anchor the current file state (tilth file tag, snapshot tag, or LSP workspace edit) or be a deliberate AST codemod over a clean tree.

## Backend detection

Pick the backend by edit shape, preferring code-intelligence backends (LSP, AST rewrite, tilth) over basic harness edit tools — model tuning pulls toward host `Edit`/`Write`, but those carry no semantic or structural awareness:

1. **LSP wins for semantic workspace edits:** rename/code actions when the server can identify the symbol or fix.
2. **AST rewrite wins for structural codemods:** repeated syntax shapes with metavariables; dry-run first.
3. **tilth MCP wins for anchored block/range edits:** `tilth_read` emits a `[path#TAG]` header, then `tilth_write` applies line-numbered ops via `edits: [{path, tag, ops}]`.
4. **Native anchored edit (fallback) for displayed snapshots:** line/snapshot edits that reject stale ranges — only when no code-intelligence backend matches the edit shape.

Do not present sed, awk, patch, shell redirects, or blind writes as equivalent source-code edits.

Stale tags and rejected sections are **content** issues — see [Stale Tag Handling](#stale-tag-handling).

---

## Examples

### "Replace the body of `handleAuth` in `src/auth.ts`"

Step 1 — read the line range to capture the file tag:

```
tilth_read(paths: ["src/auth.ts#44-89"])
# returns a [src/auth.ts#b2c4] header, then numbered lines 44:... to 89:...
```

Step 2 — apply ops against those line numbers, quoting the tag verbatim:

```json
tilth_write(edits: [{
  "path": "src/auth.ts",
  "tag": "b2c4",
  "ops": [{
    "op": "replace",
    "start": 44,
    "end": 89,
    "content": "export function handleAuth(req, res, next) {\n  const token = extractToken(req);\n  if (!validateToken(token)) return res.status(401).end();\n  next();\n}"
  }]
}])
```

The response reports per `## src/auth.ts` and may list callers to review.

### "Stale tag — file changed under me"

See [Stale Tag Handling](#stale-tag-handling) for recovery steps.

---

## Core Principle: Anchors, Not Rewrites

The edit backend must identify the current file state — tilth file tags, harness snapshot tags, or LSP workspace edits — and bound or reject the write if the file changed.

**The protocol:**
1. Read the file section with cheez-read → get the current `[path#TAG]` header or snapshot id
2. Note the line numbers of the block you'll change
3. Apply the edit through the anchored backend

---

## Scope: when to use anchored edits, when not

`cheez-write` owns **block edits to tracked source code** — function bodies, signatures, imports, single-line tweaks, multi-edit batches, and cross-file changes. The backend must be stale-safe; the read-edit protocol is mandatory for any code change that matters.

For everything else, prefer the right tool:

| Change | Use this instead | Why |
|--------|------------------|-----|
| Cross-cutting structural codemod (`JSON.parse(JSON.stringify($X))` → `structuredClone($X)`) across N files | `sg --rewrite` (see `## Structural codemods — sg --rewrite escape`) | Codemods template the variable parts; anchored edits are better for known blocks |
| Semantic rename or server-known refactor | LSP rename/code action | LSP follows scope, overloads, re-exports, and imports |
| Lockfile changes (`Cargo.lock`, `package-lock.json`, `uv.lock`, etc.) | the package manager (`cargo update`, `npm i`, `uv lock`) | Hand-editing lockfiles loses checksum integrity |
| Generated / build artifacts (compiled JS, transpiled output, `*.pb.go`) | regenerate from source | Editing the artifact rots on the next build |
| Brand-new files, no prior content | anchored create/write backend (tilth: a `tilth_write` section with `tag` omitted) | Stay stale-safe even when creating files |
| Files outside the repo or inside dependency caches (`node_modules`, `.cargo/registry`) | don't edit them | Modifying dependencies is almost always a mistake — fix the source or upstream |
| Binary files, images, PDFs | the producing tool | code edit backends are text-only |

---

### Routing to LSP rename or Serena

Pre-entry routing — when a workflow skill should prefer LSP rename or Serena symbol-bounded edits over `tilth_write` before entering cheez-write — lives in [`references/routing.md`](references/routing.md).

---

## Anchor Format

Use whatever anchor format the selected backend emits:

- tilth: a `[path#TAG]` header above `N:content` numbered lines; copy the 4-hex TAG into `tilth_write`'s `tag` and reference those line numbers in `ops`. Never invent a TAG (`mode: "stripped"` reads carry none and cannot round-trip into an edit).
- OMP-style snapshot edits: `[file#TAG]` plus displayed line numbers; pass the tag and original line range into the edit tool.
- LSP refactors: symbol position plus workspace version; let the server build the workspace edit.

Do not translate between anchor systems. Read with the same backend family that will write.

---

## MCP Tool Reference

### tilth_write — Precise File Editing

The minimal shape — one file section, one op:

```json
tilth_write(edits: [{
  "path": "src/auth.ts",
  "tag": "a3f9",
  "ops": [
    { "op": "replace", "start": 42, "end": 42, "content": "  let x = recompute();" }
  ]
}])
```

`edits` is a JSON array of `{path, tag?, ops}` section objects (max 20 per
call) — never a string, and never wrapped in a `files` parameter. Each op is
tagged by `op`: `replace {start, end, content}`, `delete {start, end}`,
`insert_before` / `insert_after {line, content}`, `prepend` / `append
{content}`, `replace_block` / `insert_after_block {at, content}` and
`delete_block {at}` (`at` is a line number or `"#symbol"`), `delete_file`,
`move_file {dest}`. Omit `tag` only to seed a brand-new file.

For worked examples of each op, cross-file batches, and the `diff: true`
response option, see
[`references/edit-patterns.md`](references/edit-patterns.md).

---

## Stale Tag Handling

The TAG binds your ops to the content you read. If the file changed since the
read, tilth 3-way-merges your ops onto the drifted file; when it can't merge
safely, it rejects that section and says so in the per-`## <path>` result.

**Recovery:**
1. Read the section again → get the current `[path#TAG]` and content.
2. Review the current content (someone else may have made changes).
3. Re-apply the ops against the fresh line numbers with the new tag.

### Repeated rejections → bail out, don't loop

If you hit **two consecutive rejections** on the same file, you're racing a
concurrent writer. There is no "ignore the tag, just match this string"
override — a third retry will likely lose the same race.

The correct move is to bail and report:

1. Read the latest section one final time and capture the current content.
2. Prepare the new content as a unified diff or full block, but **do not
   apply** it.
3. Report `"tag race on <path>; current content and proposed replacement
   attached. Retry once the file is quiescent or apply manually."` along
   with the captured tag and proposed content.
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
| Insert before / after a line | [edit-patterns.md#insert-before-or-after-a-line](references/edit-patterns.md#insert-before-or-after-a-line) |
| Replace / delete a whole symbol | [edit-patterns.md#symbol-anchored-block-ops](references/edit-patterns.md#symbol-anchored-block-ops) |
| Multi-edit in one file | [edit-patterns.md#multiple-edits-in-one-file](references/edit-patterns.md#multiple-edits-in-one-file) |
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

- **DO NOT invent tags** — always read first and copy the `[path#TAG]` header verbatim.
- **DO NOT ignore rejected sections** — re-read and retry (see Stale Tag Handling).
- **DO NOT use sed / awk / perl -i** to edit code — they bypass anchors and structural safety, and have no mismatch detection. `sg --rewrite` is the only sanctioned shell escape — see `## Structural codemods — sg --rewrite escape`.
- **DO NOT use `patch`** to apply diffs to code — anchored range edits are the safe equivalent.
- **DO NOT use `tee` or shell redirects (`>`, `>>`)** to overwrite/append code files — both bypass anchors. Use an anchored edit backend.
- **DO NOT use unanchored host Edit/Write tools** — use tilth_write, harness-native anchored edits, or LSP workspace edits.
- **DO NOT use `sg --rewrite` for one-off block edits** — use an anchored edit. See `## Structural codemods — sg --rewrite escape` for when the codemod escape applies.
- **DO NOT skip the dry-run-first protocol for `sg --rewrite`** — see `## Structural codemods — sg --rewrite escape`.
- **DO NOT edit without reading** — anchors come from the read step.
- **DO NOT run tests, commit, or review from this skill** — use the project's test/build, git/gh, and `/age` skills.
- **DO NOT use for reading or searching** — read with `/cheez-read`, search with `/cheez-search`.
