# Routing out of tilth

Name-shaped or text-shaped -> stay in `tilth_search`. Type-grounded -> route to LSP/Serena before entering cheez-search. Cross-repo questions are outside cheez-search's single-repo scope.

---

## When LSP beats tilth (if your harness has one)

**easy-cheese does not install LSP** -- it is whatever language servers your harness already exposes (Claude Code LSP plugins, Zed / VS Code language servers, etc.). When an LSP is reachable for the file's language and the question is **type-grounded**, prefer the LSP method over tilth. Tree-sitter sees syntax, not types -- it cannot disambiguate `var x = GetValue()` (keyword or type?) or pick between two `pop` functions imported from different modules. LSP runs the actual language server and resolves these.

| Question | LSP method (when available) | Why LSP wins |
|----------|-----------------------------|---------------|
| "What's the resolved return type / generic instantiation of X?" | `textDocument/hover` | tilth sees syntax, not types -- hover returns the resolved signature |
| "Who implements interface / trait / abstract class Y?" | `textDocument/implementation` | Honors aliased imports, generics, and re-exports; tilth's name match misses these |
| "Where is this exact symbol used, accounting for shadowing and module scope?" | `textDocument/references` | Scope-respecting; tilth's callers query is name-shaped |
| "Where is the *type* (not the value) of X declared?" | `textDocument/typeDefinition` | Resolves through type aliases and generics |
| "Are there type errors in this file?" | `textDocument/diagnostic` / pull-diagnostic | Only LSP runs the language server's typechecker |

If no LSP is installed for the language, or the file is in a broken / incomplete state where the server cannot resolve, fall back to tilth -- `tilth_search` still finds the symbol by name even when no semantic resolution is possible. tilth also wins on speed at scale, polyglot queries (one call across Rust + TS + Python), error-tolerant parses, and content / regex queries that LSP does not index.

---

## When Serena beats tilth (if your harness has it)

[Serena](https://github.com/oraios/serena) is an LSP-driven MCP that exposes the LSP queries above as named tools. When Serena is configured for the codebase (`.serena/project.yml` present) and the question is type-grounded, the **calling workflow skill** should route directly to Serena rather than entering `/cheez-search` -- same semantics as the abstract LSP methods above, with concrete tool names:

| Question | Serena tool | Why it beats tilth |
|----------|-------------|--------------------|
| "Who *really* references X, accounting for aliased imports and shadowing?" | `mcp__serena__find_referencing_symbols` | Type-aware xrefs; tilth's `kind: "callers"` is name-shaped |
| "What implements interface / trait Y?" | `mcp__serena__find_implementations` | Honors generics and re-exports; tilth surfaces every textual match |
| "Where is the declaration of X (following imports)?" | `mcp__serena__find_declaration` | Walks the import graph; tilth returns every definition with that name |
| "Find symbol X across the project, semantically" | `mcp__serena__find_symbol` | LSP-indexed; pair with `mcp__serena__get_symbols_overview` for a file's symbol table |

`/cheez-search` itself stays tilth-only -- the `allowed-tools` frontmatter does not (and should not) include `mcp__serena__*`. The routing decision happens in the workflow skill *before* it enters `/cheez-search`, matching the redirection-map pattern above. If Serena is unavailable, `.serena/project.yml` is missing, or the symbol isn't LSP-resolvable (broken or generated code), the workflow skill enters `/cheez-search` and uses `tilth_search` -- note "Serena unavailable" in evidence so confidence calibration reflects that the xref wasn't type-validated. tilth also remains the right call for polyglot one-call queries, content / regex search, and any case where speed at scale matters more than type fidelity.

---
