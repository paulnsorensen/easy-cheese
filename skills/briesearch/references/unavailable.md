# Unavailable providers

A provider is an implementation detail; the routed capability is the contract. Use the next route that `providers` lists for the capability. The order is a CLI, then an MCP tool in your tool list, then a native harness tool. `git-host` uses the host GitHub primitive, then `gh`. This order covers only the `providers` capabilities. Wiki and local code keep their own routing rules. See `providers.md`.

## Capability fallbacks

| Capability | Equivalent fallbacks | Confidence impact |
| --- | --- | --- |
| Library/API documentation | Any `docs` route, official vendor docs or `llms.txt` through a `web-extract` route, package docs or README | Lower only if version/authority coverage weakens |
| Current-web discovery/extraction | Any `web-search` or `web-extract` route, including Jina Reader through `curl` | Lower only if freshness or verification coverage weakens |
| Scholarly literature | Any `papers` route, or the publisher page through a `web-extract` route | Lower only if the paper or its version remains unread |
| Repository knowledge/wiki | Hallouminate, llm-wiki, bounded Markdown ADR/wiki reads | Lower only if rationale/decision coverage remains incomplete |
| Local code intelligence | Use alternate semantic, LSP, AST, or text backends. Follow the [shared routing contract](../../cheese/references/code-intelligence-routing.md). | Lower only if the backend cannot inspect critical local evidence precisely |
| Git hosting/examples | Any `git-host` route or host-scoped web search/open | Lower only when hosted state or examples are critical and uncovered |

A configured MCP server can fail to connect. Treat a server that is absent from your tool list as unavailable, and use the next route. A model summary from a native fetch tool is discovery evidence. It does not replace a raw retrieval for a quoted claim.

Direct URLs and user URLs are candidate sources, not provider operations. Inspect their content with a provider retrieval tool before you use it. The user URL exemption in `synthesis.md` applies only to link checks.

## Reporting a substitution

Report it once after the routing block:

```text
UNAVAILABLE: context7 MCP is configured but not loaded. Using the ctx7 CLI for
Library/API documentation. Coverage remains authoritative; no confidence change.
```

If the replacement is weaker, name the lost coverage. Then apply the matching cap from `synthesis.md`. Do not lower confidence because the preferred provider is absent. Do not retry the same unavailable provider. Do not change the question silently.

## When to stop

Stop and ask the user when:

- The user explicitly requires a provider that is unavailable.
- A required capability has no usable provider or evidence source.
- Every equivalent fallback leaves a critical claim uncovered.
- Continuing would require fabricating information.
