# Pre-entry routing: LSP rename and Serena

These decisions happen in the **calling workflow skill** before entering `/cheez-write`.
Once inside cheez-write, `tilth_edit` is the only edit tool.

## When LSP rename beats tilth_edit (if your harness has one)

**easy-cheese does not install LSP** — it is whatever language servers your harness already exposes. There is one editing operation where an available LSP materially outperforms `tilth_edit`: **type-aware rename** of a symbol across the project.

| Edit | Use this instead | Why LSP wins |
|------|------------------|---------------|
| Rename a function / class / variable across all type-correct usages, including aliased re-exports and generic instantiations | `textDocument/rename` (or the harness's rename refactor) | Returns a typechecker-validated `WorkspaceEdit`; covers aliased imports without textual collisions, and skips coincidental name matches in unrelated scopes. `tilth_edit` would need a separate read-edit cycle per call site, and `sg --rewrite` matches on syntax not type identity (overshoots on shadowed names, undershoots on aliased re-exports) |

For everything else — block edits, signature changes, body rewrites, hand-written codemods — `tilth_edit` (one-off) and `sg --rewrite` (cross-cutting) remain the right tools. LSP rename is narrowly the best fit for **identifier renames specifically**; nothing else in LSP's edit surface improves on the cheez-write protocol.

If no LSP is installed, or the rename touches a symbol the typechecker can't resolve (broken code, generated bindings), fall back to `sg --rewrite` with the dry-run-first protocol — see "Structural codemods" in [SKILL.md](../SKILL.md).

## When Serena beats tilth_edit for symbol-bounded edits (if your harness has it)

[Serena](https://github.com/oraios/serena) is an LSP-driven MCP that exposes symbol-bounded edits as named tools. When Serena is configured for the codebase (`.serena/project.yml` present) and the edit is symbol-shaped, the **calling workflow skill** should route directly to Serena rather than entering `/cheez-write`:

| Edit | Serena tool | When to prefer over `tilth_edit` |
|------|-------------|----------------------------------|
| Rename a symbol type-correctly across the project | `mcp__serena__rename_symbol` | The LSP rename case above — Serena gives it a concrete tool |
| Replace a whole function / class body by name | `mcp__serena__replace_symbol_body` | Skips the "read for anchors → edit" round-trip when the boundary is a named symbol |
| Insert before / after a named symbol (e.g. add a method to a class, or a function next to its sibling) | `mcp__serena__insert_before_symbol`, `mcp__serena__insert_after_symbol` | No anchor needed for a moving boundary |
| Delete a symbol and check for orphaned references | `mcp__serena__safe_delete_symbol` | Validates xrefs before the cut — `tilth_edit` would happily strand callers |

`/cheez-write` itself stays tilth-only — its `allowed-tools` frontmatter does not include `mcp__serena__*` and shouldn't. The routing decision happens in the workflow skill *before* it enters `/cheez-write`.

**Caveat — no race-safe hash anchors.** Serena's edits rely on LSP and file mtime, not the content-hash check that makes `tilth_edit` race-safe. The workflow skill should route to Serena only when the file is quiescent (no parallel writers, no in-flight `/cook` or `/cure` on the same path). Route back into `/cheez-write` whenever concurrency safety dominates, the symbol isn't LSP-resolvable (broken or generated code), the edit is sub-symbol (one line inside a function), or Serena is unavailable.
