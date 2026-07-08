# Pre-entry routing: semantic and symbol-bounded edits

The **calling workflow skill** selects the stale-safe backend before entering `/cheez-write`, matching it to the edit shape: tilth hash anchors, LSP workspace edits, Serena symbol edits, harness-native snapshot edits, or a dry-run-first AST codemod.

## When LSP rename beats line/range edits

LSP availability: easy-cheese does not install LSP — it's whatever language servers the harness exposes. There is one editing operation where an available LSP materially outperforms line/range edits: **type-aware rename** of a symbol across the project.

| Edit | Use this instead | Why LSP wins |
|------|------------------|---------------|
| Rename a function / class / variable across all type-correct usages, including aliased re-exports and generic instantiations | `textDocument/rename` (or the harness's rename refactor) | Returns a typechecker-validated `WorkspaceEdit`; covers aliased imports without textual collisions, and skips coincidental name matches in unrelated scopes. Line/range edits would need a separate read-edit cycle per call site, and `sg --rewrite` matches on syntax not type identity (overshoots on shadowed names, undershoots on aliased re-exports) |

For everything else — block edits, signature changes, body rewrites, hand-written codemods — use a stale-safe line/range backend for one-off edits and `sg --rewrite` for cross-cutting structural codemods. LSP rename is narrowly the best fit for **identifier renames specifically**; it is not a general replacement for anchored edits.

If no LSP is installed, or the rename touches a symbol the typechecker can't resolve (broken code, generated bindings), fall back to `sg --rewrite` with the dry-run-first protocol — see "Structural codemods" in [SKILL.md](../SKILL.md).

## When Serena beats line/range edits for symbol-bounded edits

Serena ([oraios/serena](https://github.com/oraios/serena)) is an LSP-driven MCP that exposes symbol-bounded edits as named tools; when it is configured (`.serena/project.yml` present) and the edit is symbol-shaped, the **calling workflow skill** may route directly to Serena rather than using a line/range edit:

| Edit | Serena tool | When to prefer over line/range edits |
|------|-------------|----------------------------------|
| Rename a symbol type-correctly across the project | `mcp__serena__rename_symbol` | The LSP rename case above — Serena gives it a concrete tool |
| Replace a whole function / class body by name | `mcp__serena__replace_symbol_body` | Skips the "read for anchors → edit" round-trip when the boundary is a named symbol |
| Insert before / after a named symbol (e.g. add a method to a class, or a function next to its sibling) | `mcp__serena__insert_before_symbol`, `mcp__serena__insert_after_symbol` | No anchor needed for a moving boundary |
| Delete a symbol and check for orphaned references | `mcp__serena__safe_delete_symbol` | Validates xrefs before the cut — a raw line/range edit would happily strand callers |

`/cheez-write` is not tilth-only. Its invariant is stale safety: the chosen backend must anchor the current file state, be typechecker-owned, or be a bounded AST codemod run after a dry run.

**Caveat — no race-safe hash anchors.** Serena's edits rely on LSP and file mtime, not the content-hash check that makes tilth hash anchors race-safe. The workflow skill should route to Serena only when the file is quiescent (no parallel writers, no in-flight `/cook` or `/cure` on the same path). Use a hash/snapshot anchored edit whenever concurrency safety dominates, the symbol isn't LSP-resolvable (broken or generated code), or the edit is sub-symbol (one line inside a function).
