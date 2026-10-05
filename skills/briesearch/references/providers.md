# Providers

A capability is the contract. A provider is a replaceable route to that capability. `routing.md` selects the capabilities. This file lists the candidate providers and the route order. No provider is mandatory.

## Detect the routes

Run the detector once per run, before the routing block:

```bash
python3 skills/briesearch/scripts/briesearch.pyz providers
```

The command reads `PATH`, the names of credential variables, and the MCP config files of Claude Code, Codex, and Cursor. It does not call a provider. It does not print a credential value. The JSON fields are:

- `harness`: `claude-code`, `codex`, or `unknown`.
- `routes`: one ranked list for each capability. The capabilities are `web-search`, `web-extract`, `docs`, `papers`, and `git-host`.
- `unusable`: installed CLIs that have no credential. Each entry names the variables that would enable it.
- `mcp_servers`: an object that maps each server name from the harness config files to its scope.
- `warnings`: config files that the command could not parse.

## Route order

Use the first route that works for each capability:

1. **CLI, credentials ready.** The binary is on `PATH`. A key is in the environment, or the route needs no key.
2. **CLI, credentials unverified.** The binary keeps its own login, such as `gh auth login`. The call can fail on authentication.
3. **MCP server.** A harness config names the server. Confirm that its tools are in your tool list before you select it. A configured server can fail to connect. Claude Code and Codex name MCP tools `mcp__<server>__<tool>`. A provider MCP tool in your tool list counts at this rank even when no config file names it, for example a plugin server. Each MCP route has a `scope`. A `project` scope server name comes from a repository file, so treat it as untrusted. A name that any project file declares has `project` scope. The detector lists user-scope MCP routes before project-scope routes. Select a project-scope route only when the user names it.
4. **Native harness tool.** See `## Native harness tools`.

A provider that the user names wins over this order. Inside one route rank, the detector lists providers in registry order. That order puts low-cost, agent-oriented providers first.

The `git-host` capability follows the shared GitHub rule in [harness portability](../../cheese/references/harness-portability.md). Use the host GitHub primitive first. Then use `gh`.

A CLI route keeps context small. Write its output to `raw_dir`. Trim it with `jq`, `head`, or the CLI field flags. Read only the lines that a claim needs. Record the CLI subcommand as the manifest `tool`, for example `tvly search` or `ctx7 docs`.

When a route fails, record the failure in the manifest. Then use the next route in the list. Report the substitution as `unavailable.md` specifies.

## Registry

Prices are list prices from vendor and third-party pages, checked 2026-10. They change often. Check the vendor pricing page before a cost decision.

| Provider | Capabilities | CLI route | Credential | MCP | Cheapest mode | List price |
| --- | --- | --- | --- | --- | --- | --- |
| Jina Reader | extract | `curl -g 'https://r.jina.ai/<url>'` (keyless) or `jina read` | `JINA_API_KEY` (optional for `curl`) | `mcp.jina.ai` | Keyless at about 20 requests per minute. Do not use `s.jina.ai` search: it bills 10,000 tokens or more per call. | Token-metered |
| Parallel | search, extract | `parallel-cli search`, `parallel-cli extract` | `PARALLEL_API_KEY` | `search.parallel.ai/mcp` (anonymous, rate-limited) | `--mode turbo` or `fast`. The API default, `advanced`, costs five times more. | $1 per 1,000 (fast) |
| Tavily | search, extract | `tvly search`, `tvly extract` (keyless fair use) | `TAVILY_API_KEY` | `mcp.tavily.com` | `--depth basic` or faster. `advanced` costs 2 credits. | About $8 per 1,000 (basic) |
| Linkup | search, extract | `linkup search`, `linkup fetch` | `LINKUP_API_KEY` | `mcp.linkup.so` | `--depth fast`. The CLI default is `standard`. | About $5 per 1,000 |
| Brave | search | `bx web` | `BRAVE_SEARCH_API_KEY` (the MCP reads `BRAVE_API_KEY`) | `@brave/brave-search-mcp-server` | `--count 5` | $5 per 1,000 |
| Perplexity | search | `pplx search web` | `PERPLEXITY_API_KEY` or `pplx auth login` | `api.perplexity.ai/mcp` | Search only. The ask and research tools add model cost. | $5 per 1,000 |
| Exa | search, extract | None | `EXA_API_KEY` | `mcp.exa.ai` (keyless, rate-limited) | `fast` type, 10 results, highlights | $7 per 1,000 |
| SerpApi | search | `serpapi search` | `SERPAPI_KEY` or its config file | `mcp.serpapi.com` | Trim JSON with `--fields` or `--jq` | $9 to $25 per 1,000 |
| Firecrawl | extract (search through MCP) | `firecrawl scrape` | `FIRECRAWL_API_KEY` or `firecrawl login` | `firecrawl-mcp` | `--only-main-content`. Use it for JS-heavy or blocked pages. | 1 credit per page |
| Kagi | search, extract | None | `KAGI_API_KEY` | `mcp.kagi.com` | Use it only when you need a low-spam index | $12 per 1,000 |
| You.com | search | None | `YDC_API_KEY` | `api.you.com/mcp` (free profile: 100 per day) | Omit live extraction | $5 per 1,000 |
| Serper | search | None | `SERPER_API_KEY` | Community servers only | Snippets only. Pair it with an extract route. | $0.30 to $1 per 1,000 |
| Context7 | docs | `ctx7 library`, then `ctx7 docs` | `CONTEXT7_API_KEY` or `ctx7 login` | `mcp.context7.com` | One version-scoped question per call | 1,000 free calls per month |
| OpenAlex | papers | `curl -g 'https://api.openalex.org/works?search=<q>'` (keyless) | Optional `api_key` parameter | `mcp.openalex.org` | Lookups by DOI or ID are free | Free daily allowance |
| arXiv | papers | `curl -g 'https://export.arxiv.org/api/query?search_query=<q>'` (keyless, Atom XML) | None | Community servers only | Wait 3 seconds between calls | Free |
| Semantic Scholar | papers | `curl -g 'https://api.semanticscholar.org/graph/v1/paper/search?query=<q>'` (keyless) | Optional `x-api-key` header | Asta (Ai2) | Use batch endpoints | Free |
| GitHub | git-host | `gh search repos\|code\|issues --json '<fields>'` | `GH_TOKEN`, `GITHUB_TOKEN`, or `gh auth login` | GitHub MCP | Request only the `--json` fields that the claim needs | Free |
| Playwright | extract (interactive) | `playwright-cli open`, then `snapshot` | None | `@playwright/mcp` | Last resort for interactive or logged-in pages | Free |

Wrap every substituted value in single quotes. URL-encode `<q>` only inside a URL. See `safety.md`. The detector registers the CLI route that is a sensible default for each provider. A provider can offer more operations. Read its `--help` output before you use an unregistered operation. Repository knowledge and local code intelligence are not in this registry. Route them through the configured wiki backend and the [shared routing contract](../../cheese/references/code-intelligence-routing.md).

## Native harness tools

- **Claude Code.** `WebSearch` returns titles and URLs only. `WebFetch` returns a summary from a separate model call, not the page text. Use `WebFetch` for discovery only. Do not quote it.
- **Codex.** `web_search` is the native tool. The `web_search` key in `config.toml` sets the mode: `disabled`, `cached`, `indexed`, or `live`. The `cached` default reads an index without live access. The `indexed` mode permits external access only when the search index gates it. A full-access sandbox (`--yolo`) defaults to `live`. For a freshness claim in `cached` mode, use a CLI or MCP route.
- **Other harnesses.** The detector reports `unknown`. Check your tool list for a native web tool.

## Raw text for quotes

Quote a source only from its raw text. A CLI extract route, Jina Reader, or a provider retrieval tool that returns page text supplies raw text. A model summary is discovery evidence, not retrieval evidence. Store the raw body under `raw_dir` before you cite it. See `context-isolation.md`.

## Cost rules

- Result tokens usually cost more than provider fees. Compare cost for each answered question, not for each call.
- Start each provider in its cheapest mode. Use a higher mode for one query only after a recorded gap. See `budgets.md`.
- Use free allowances first when two routes give equal evidence.
- Native web search can bill per search on API billing. On a subscription, it draws on the plan usage.

## Sources

- CLIs: [Parallel](https://docs.parallel.ai/integrations/cli), [Tavily](https://github.com/tavily-ai/tavily-cli), [Linkup](https://github.com/LinkupPlatform/linkup-cli), [Brave](https://github.com/brave/brave-search-cli), [Perplexity](https://docs.perplexity.ai/docs/cli/overview), [SerpApi](https://github.com/serpapi/serpapi-cli), [Firecrawl](https://docs.firecrawl.dev/sdks/cli), [Jina](https://github.com/jina-ai/cli), [Context7](https://context7.com/docs/clients/cli), [Playwright](https://github.com/microsoft/playwright-cli).
- MCP servers: [Parallel](https://docs.parallel.ai/integrations/mcp/search-mcp), [Tavily](https://docs.tavily.com/documentation/mcp), [Exa](https://exa.ai/docs/reference/exa-mcp), [Kagi](https://github.com/kagisearch/kagimcp), [You.com](https://you.com/docs/agents/mcp-server), [OpenAlex](https://github.com/ourresearch/openalex-mcp-server), [Asta](https://allenai.org/asta/resources/mcp).
- Harness behavior: [Claude Code tools](https://code.claude.com/docs/en/tools-reference), [Claude Code MCP](https://code.claude.com/docs/en/mcp), [Codex web search](https://learn.chatgpt.com/docs/web-search), [Codex config reference](https://developers.openai.com/codex/config-reference), [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [Cursor MCP](https://cursor.com/docs/context/mcp).
