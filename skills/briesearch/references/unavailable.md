# Unavailable sources

Optional MCP servers (Context7, Tavily, tilth) are not always present. Fallbacks exist, but evidence quality drops — state that explicitly.

## Per-source fallbacks

| Source | If MCP missing | Confidence impact |
| --- | --- | --- |
| Context7 | Read repo docs, package README, vendor pages, then web search | Cap at `speculating` for version-specific questions |
| Tavily | WebFetch (host fetch) for verify/extract; host web search or user-provided links for discovery | Cap at `speculating` when freshness matters |
| Codebase (`cheez-*`) | Fall back to Serena or LSP, `sg`, `ripgrep`, `find`, and targeted reads | Cap at `speculating` when local precedent is central |
| GitHub (`gh`) | Note absence; user-supplied URLs are acceptable | Skip with a confidence note |

## Reporting an unavailable source

Once per session, after the routing block:

```text
UNAVAILABLE: Tavily MCP not loaded. Falling back to WebFetch for link verification and host web search for discovery.
Freshness-sensitive answers will be capped at `speculating`.
```

Do not retry. Do not silently swap to a different question. The cap is real and the user reads the same line you do.

## When to refuse instead of fall back

Stop and ask the user when:
- The question explicitly demands a source that is unavailable (e.g., "use Context7 for this").
- All routed sources are unavailable.
- A fallback would require fabricating information.
