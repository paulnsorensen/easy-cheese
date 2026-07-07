# cheez-read: When Another Tool Fits Better

Use this reference when cheez-read is not the right choice. The main skill covers the happy path; these tables cover the route-elsewhere branch.

## When NOT to invoke `/cheez-read`

Inside `/cheez-read`, the contract is backend-aware rather than tilth-only: use tilth when available, otherwise use a harness-native bounded read/list backend or LSP when it provides fresh source context and enough line/snapshot evidence for follow-up edits. The reads below are **out of scope** for the skill — don't enter cheez-read for them in the first place. They're listed here so workflow skills know where to route instead, consistent with the README rule "anything that touches source code goes through `cheez-*`; everything else stays on host tools".

| File (don't use cheez-read) | Route to | Why |
|-----------------------------|----------|-----|
| Binary content (images, PDFs) | host `Read` (multimodal) from the calling workflow skill | tilth can't render these |
| Streaming output, process logs, huge CSVs | host `Bash` with `head`/`tail`, `awk`, `jq` from the calling workflow skill | Format-specific tools beat outline mode here |
| Lockfiles, minified bundles, generated artifacts | don't read by hand — regenerate from source | tilth deliberately skips these |
| Files outside the repo (system paths, sibling worktrees, `~/...`) | host `Read` from the calling workflow skill | tilth is repo-scoped (see above) |
| Dependency source (`node_modules`, `.cargo/registry`, `site-packages`, vendor caches) | LSP `textDocument/definition` from the calling workflow skill if a server is reachable; otherwise don't read by hand | Reading dependency source by hand is almost always wrong; the LSP resolves the right module version |

If the file is code in this repo, **always enter cheez-read first** so it can choose a freshness-aware backend. Prefer tilth when edit tags are available; otherwise use the harness-native snapshot/read path when it preserves stale-write safety for the next edit.

## When LSP beats broad read backends (if the harness has one)

LSP availability: easy-cheese does not install LSP — it's whatever language servers the harness exposes. When an LSP is reachable for the file's language and the navigation question is type-grounded, prefer the LSP method:

| Goal | LSP method (when available) | Why LSP wins |
|------|------------------------------|--------------|
| Jump to where a symbol is *defined*, following imports / re-exports | `textDocument/definition` | Resolves the actual import graph; broad syntax backends surface definitions by name |
| Read the *resolved* type / generic instantiation at a call site | `textDocument/hover` | Returns the typechecker's view of the symbol, not just the source declaration |
| Open the file declaring the *type* of a value | `textDocument/typeDefinition` | Walks through type aliases and generics |
| Browse symbols across the whole project, semantically ranked | `workspace/symbol` | LSP indexes the project's type graph; syntax/read backends parse the tree |

If no LSP is installed for the language, or the file is in a broken / incomplete state where the server cannot resolve, use the selected freshness-aware read backend. Tilth remains preferred when present because it provides outline reading, tag-anchored prep for edits, polyglot directory listings, and `.gitignore`-aware token estimates in one backend.

## When Serena beats broad read backends for symbol-table reads (if your harness has it)

Serena ([oraios/serena](https://github.com/oraios/serena)) is an LSP-driven MCP exposing LSP queries as named tools. When Serena is configured (`.serena/project.yml` present) and the read is symbol-shaped, the **calling workflow skill** should route directly to Serena rather than entering `/cheez-read`:

| Goal | Serena tool | Why |
|------|-------------|-----|
| Just the symbol table of one file (no source lines) | `mcp__serena__get_symbols_overview` | Cheaper than tilth outline mode — LSP-indexed, no parse pass |
| Read a single symbol's body by name (no line range needed) | `mcp__serena__find_symbol` with body inclusion | Skips the "outline → drill into 44-89" round-trip |

The routing decision happens in the workflow skill *before* it enters `/cheez-read`. Enter `/cheez-read` when you need edit anchors, repo-aware listing, token-budgeted preview, or when Serena is unavailable. Serena gives you the symbol; Tilth or a native snapshot backend gives you anchors — if an edit follows, prefer a backend that already provides the stale-safe anchor you will pass to cheez-write. See [`cheez-write`](../../cheez-write/SKILL.md) for the symmetric symbol-bounded edit guidance.
