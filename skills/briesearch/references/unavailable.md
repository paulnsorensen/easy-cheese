# Unavailable sources

Optional MCP servers (Context7, Tavily, code-review-graph, tilth) are not always present. Fallbacks exist, but evidence quality drops — surface that honestly.

## Per-source fallbacks

| Source | If MCP missing | Confidence impact |
| --- | --- | --- |
| Context7 | Read repo docs, package README, vendor pages, then web search | Cap at `speculating` for version-specific questions |
| Tavily | Host web search or user-provided links | Cap at `speculating` when freshness matters |
| Codebase (cheez-*) | Fall back to Serena or LSP, `sg`, `ripgrep`, `find`, and targeted reads | Cap at `speculating` when local precedent is central |
| code-review-graph (full tool list in [README → code-review-graph](../../../README.md#code-review-graph-review-impact-radius-architecture-semantic-search)) | Use `tilth_deps` + `cheez-search` callers (`tilth_search kind: "callers"`) for blast radius; skip cross-repo, semantic search, and architecture framing | Cap at `speculating` for cross-repo or large-architecture questions |
| GitHub (`gh`) | Note absence; user-supplied URLs are acceptable | Skip with a confidence note |

## Reporting an unavailable source

Once per session, after the routing block:

```text
UNAVAILABLE: Tavily MCP not loaded. Falling back to host web search.
Freshness-sensitive answers will be capped at `speculating`.
```

Do not retry. Do not silently swap to a different question. The cap is real and the user reads the same line you do.

## When to refuse instead of fall back

Stop and ask the user when:
- The question explicitly demands a source that is unavailable (e.g., "use Context7 for this").
- All routed sources are unavailable.
- A fallback would require fabricating information.
