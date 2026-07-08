# Routing among search backends

Name-shaped or text-shaped queries stay in the chosen semantic source-search backend: tilth when available, otherwise native AST/source search that preserves code context. Type-grounded questions route to LSP/Serena before entering cheez-search. Cross-repo questions are outside cheez-search's single-repo scope.

---

## When LSP beats name/text search (if your harness has one)

LSP availability: easy-cheese does not install LSP — it's whatever language servers the harness exposes. When an LSP is reachable for the file's language and the question is **type-grounded**, prefer the LSP method over name/text search. Tree-sitter sees syntax, not types -- it cannot disambiguate `var x = GetValue()` (keyword or type?) or pick between two `pop` functions imported from different modules. LSP runs the actual language server and resolves these.

| Question | LSP method (when available) | Why LSP wins |
|----------|-----------------------------|---------------|
| "What's the resolved return type / generic instantiation of X?" | `textDocument/hover` | name/text search sees syntax, not types -- hover returns the resolved signature |
| "Who implements interface / trait / abstract class Y?" | `textDocument/implementation` | Honors aliased imports, generics, and re-exports; a name match misses these |
| "Where is this exact symbol used, accounting for shadowing and module scope?" | `textDocument/references` | Scope-respecting; a callers query is name-shaped |
| "Where is the *type* (not the value) of X declared?" | `textDocument/typeDefinition` | Resolves through type aliases and generics |
| "Are there type errors in this file?" | `textDocument/diagnostic` / pull-diagnostic | Only LSP runs the language server's typechecker |

If no LSP is installed for the language, or the file is in a broken / incomplete state where the server cannot resolve, fall back to the selected semantic source-search backend. Tilth remains the preferred broad backend when present because it handles speed at scale, polyglot queries, error-tolerant parses, and content / regex queries that LSP does not index.

---

## When Serena beats tilth (if your harness has it)

Serena ([oraios/serena](https://github.com/oraios/serena)) is an LSP-driven MCP exposing LSP queries as named tools. When Serena is configured (`.serena/project.yml` present) and the question is type-grounded, the **calling workflow skill** should route directly to Serena rather than entering `/cheez-search` -- same semantics as the abstract LSP methods above, with concrete tool names:

| Question | Serena tool | Why it beats tilth |
|----------|-------------|--------------------|
| "Who *really* references X, accounting for aliased imports and shadowing?" | `mcp__serena__find_referencing_symbols` | Type-aware xrefs; tilth's `kind: "callers"` is name-shaped |
| "What implements interface / trait Y?" | `mcp__serena__find_implementations` | Honors generics and re-exports; tilth surfaces every textual match |
| "Where is the declaration of X (following imports)?" | `mcp__serena__find_declaration` | Walks the import graph; tilth returns every definition with that name |
| "Find symbol X across the project, semantically" | `mcp__serena__find_symbol` | LSP-indexed; pair with `mcp__serena__get_symbols_overview` for a file's symbol table |

`/cheez-search` is not tilth-only. Its invariant is semantic source-code evidence: use LSP/Serena for type-grounded questions, `sg` for syntax-shaped patterns, tilth for broad source search when available, or a harness-native AST/source-search backend when it answers the same symbol/caller/text question. Note the backend in evidence when it affects confidence.

---
