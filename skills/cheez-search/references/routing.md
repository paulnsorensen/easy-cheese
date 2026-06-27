# Routing out of tilth

Name-shaped or text-shaped -> stay in `tilth_search`. Type-grounded, concept-shaped, or cross-repo -> route out before entering cheez-search.

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

## When code-review-graph beats tilth (if your harness has it)

[`code-review-graph`](https://github.com/tirth8205/code-review-graph) is a separate, optional MCP that builds a **persistent** call graph of one or more repositories with Tree-sitter, Louvain communities, betweenness-centrality, and (with the `[embeddings]` extra) vector embeddings. Where tilth answers "where is `handleAuth`?", code-review-graph answers "what code is *about* authentication, ranked by importance and reach across all my repos?"

It wins on five questions tilth structurally cannot answer:

| Question | code-review-graph tool | Why tilth can't |
|----------|------------------------|------------------|
| Find code by *meaning*, not name ("rate-limiting logic", "session expiry handling") | `semantic_search_nodes_tool` | Embeddings rank by concept; tilth only matches identifiers and literal text |
| Search across *multiple* repos in one call | `cross_repo_search_tool` | tilth is scoped to one tree per MCP session |
| Risk-weighted blast radius (which callers actually matter, by centrality) | `get_impact_radius_tool`, `get_review_context_tool` | `tilth_deps` returns raw imports; code-review-graph weights them by graph centrality |
| Architecture framing for a large diff (hubs, bridges, communities) | `get_architecture_overview_tool`, `get_hub_nodes_tool`, `get_bridge_nodes_tool`, `list_communities_tool` | tilth has no global graph view |
| Affected execution flows for a change | `get_affected_flows_tool` | tilth follows callers one hop at a time; this returns full flows |

**Before the first query -- refresh the graph via MCP.** code-review-graph keeps a persistent graph that goes stale between sessions. From inside an agent, prefer the MCP tools over the CLI:

- Call `build_or_update_graph_tool` once at the start of a run. It's incremental -- on a warm repo this is fast.
- `semantic_search_nodes_tool` needs embeddings. Current server versions handle embedding without a separate tool call; if your server's tool list includes `embed_graph_tool`, call it once after build (embedding is the slow step -- skip it otherwise).

The CLI equivalents (`code-review-graph build` / `embed`) are for first-time setup; inside a run, the MCP tools let the agent own the lifecycle.

**When `semantic_search_nodes_tool` beats tilth.** Reach for it when the question is concept-shaped, not name-shaped:

- **Steel threads** -- trace a feature end-to-end when each layer names the concept differently (controller -> service -> repo -> migration -> telemetry). tilth makes you guess the next layer's vocabulary; embeddings surface the chain.
- **Shared concepts under divergent names** -- "where do we handle idempotency?" when the code uses `dedupeKey`, `requestSig`, `OnceToken`. Grep is blind to the concept; embeddings find it.
- **Vocabulary mismatch between spec and code** -- product says "session continuity", code says `KeepaliveToken`. Map the stakeholder term to the implementation without an SME.
- **Analog mining** -- before adding another retry / rate-limit / cache layer, ask what already exists under different names.
- **Cross-repo concept discovery** -- pair with `cross_repo_search_tool` to find auth (or any concept) across services that named it differently.
- **Onboarding orientation** -- "what's in this repo for observability?" returns conceptually adjacent nodes ranked by graph centrality. Faster first read than walking imports.

**Stay on tilth when** you know the symbol name; you need literal text or regex; you're doing a one-hop caller walk; the branch is hot and you haven't re-embedded; or the change is a mechanical rename or move.

**Two gotchas.** Ranking blends similarity with graph centrality -- `semantic_search_nodes_tool` biases toward hub nodes, sometimes against the leaf where the bug actually lives; after a hit, follow callers in tilth. Default embedding model is `all-MiniLM-L6-v2` (384-dim), which blurs nuanced distinctions like "session timeout" vs "session revocation" -- override via `CRG_EMBEDDING_MODEL` if your domain needs it.

If code-review-graph is unavailable, the cheez-search fallbacks are: name-shaped questions stay on tilth; semantic / cross-repo / architecture questions either degrade to a manual `tilth_deps` + `kind: "callers"` walk or get noted as unavailable evidence (cap confidence at `speculating`).
