# Unavailable providers

A provider is an implementation detail; the routed capability is the contract. Prefer the native easy-cheese helper/backend when present, otherwise select one evidence-equivalent provider.

## Capability fallbacks

| Capability | Equivalent fallbacks | Confidence impact |
| --- | --- | --- |
| Library/API documentation | Context7, official vendor docs/`llms.txt`, package docs or README | Lower only if version/authority coverage weakens |
| Current-web discovery/extraction | Native web open/fetch, Tavily extraction, Exa contents, or direct HTTP fetch | Lower only if freshness or verification coverage weakens |
| Repository knowledge/wiki | Hallouminate, llm-wiki, bounded Markdown ADR/wiki reads | Lower only if rationale/decision coverage remains incomplete |
| Local code intelligence | Use alternate semantic, LSP, AST, or text backends. Follow the [shared routing contract](../../cheese/references/code-intelligence-routing.md). | Lower only if the backend cannot inspect critical local evidence precisely |
| Git hosting/examples | `gh`, host integration, or host-scoped web search/open | Lower only when hosted state or examples are critical and uncovered |

Direct URLs and user URLs are candidate sources, not provider operations. Inspect their content with a provider retrieval tool before you use it. The user URL exemption in `synthesis.md` applies only to link checks.

## Reporting a substitution

Report it once after the routing block:

```text
UNAVAILABLE: Context7 is not loaded. Using official vendor llms.txt for
Library/API documentation. Coverage remains authoritative; no confidence change.
```

If the replacement is weaker, name the lost coverage and apply the matching cap from `synthesis.md`. Do not lower confidence merely because the preferred provider is absent. Do not retry the same unavailable provider or silently change the question.

## When to stop

Stop and ask the user when:

- The user explicitly requires a provider that is unavailable.
- A required capability has no usable provider or evidence source.
- Every equivalent fallback leaves a critical claim uncovered.
- Continuing would require fabricating information.
