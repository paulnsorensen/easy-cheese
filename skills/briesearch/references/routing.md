# Source routing

Decide once which sources will run, then commit. If you commit a source in routing, you must execute it (or surface its unavailability) — never silently drop it.

## Decision tree

```
Is the question about a specific library API, config, or migration?
  YES → Context7  (+ GitHub if real-world usage matters)

Is it a factual / current / vendor / "what or who or when" question?
  YES → Tavily basic search

Is it "how should I…" or a best-practice question?
  YES → Tavily advanced search  (+ Context7 when a named library is in scope)

Is it about patterns in this repo?
  YES → Codebase  (cheez-search + cheez-read)

Is it about how open-source projects solve something?
  YES → GitHub fetcher  (+ Tavily if written analysis would help)
```

## Source guide

| Source | Best for | Notes |
| --- | --- | --- |
| Context7 (MCP) | Library APIs, config, migration notes | Prefer over general web for any named dependency. |
| Tavily (MCP) | Current facts, technical articles, vendor docs, best practices | Basic for factual lookups; advanced for analysis. |
| Codebase | Local conventions, existing usage, constraints | Use `cheez-search` and `cheez-read`. |
| GitHub | Real-world OSS usage patterns | `gh` CLI or harness GitHub integration. |

## Routing block

Emit the decision compactly before fetching:

```text
ROUTING DECISION:
- Context7: YES (library: "<library>", query: "<focused question>")
- Tavily:   NO  (no current-events angle)
- Codebase: YES (local precedent matters)
- GitHub:   NO  (not looking for OSS usage patterns)
```

## Hard rule

If a source was committed in routing, spawn it. If it returns "unavailable", report that — do not silently drop a routed source because it later seems low-value.
