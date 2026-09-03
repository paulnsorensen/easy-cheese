# Capability routing

Select the required research capabilities once. Then use that selection. Run each capability marked `YES` through its selected provider. Otherwise, use an explicit fallback or report an unavailable or empty result.

## Decision tree

```text
Is the question about a library API, configuration, or migration?
  YES → Library/API documentation
         (for example Context7, official docs, vendor llms.txt)

Does it require current public facts, discovery, or page extraction?
  YES → Current-web discovery/extraction
         (for example Tavily, Exa, native web)

Is it about a past repository decision, rationale, ADR, or recorded convention?
  YES → Repository knowledge/wiki
         (for example Hallouminate, llm-wiki, Markdown ADR/wiki)

Is it about patterns or constraints in this checkout?
  YES → Local code intelligence
         (shared search/read routing contract)

Is it about hosted repository state or real-world project examples?
  YES → Git hosting/examples
         (for example gh, a Git hosting integration, host-scoped web search)

Is it multi-part, comparative, a "best" question, or a cited report?
  YES → Route every capability needed for the claims; use a deep-research
         provider only when it covers the required public-web portion.
```

## Capability guide

| Capability | Best for | Provider selection |
| --- | --- | --- |
| Library/API documentation | APIs, configuration, migration guidance, supported versions | Prefer the native documentation helper. Otherwise, use Context7, official documentation, `llms.txt`, or package documentation. |
| Current-web discovery/extraction | Current facts, announcements, maintenance signals, public pages | Prefer the native web backend. Otherwise, use one search and extraction pair, such as Tavily or Exa. |
| Repository knowledge/wiki | Prior decisions, rationale, ADRs, recorded conventions | Prefer the configured wiki backend. Examples include Hallouminate, llm-wiki, and limited Markdown ADR or wiki reads. |
| Local code intelligence | Existing use, implementations, local constraints | Follow the [shared source code routing contract](../../cheese/references/code-intelligence-routing.md). |
| Git hosting/examples | Issues, releases, commits, pull requests, and OSS use patterns | Use `gh`, a host integration, or host-specific web discovery. Treat examples as support unless the question asks about precedent. |

Prefer native easy-cheese helpers and backends when they are available. Otherwise, select one equivalent provider for each capability. Use multiple providers only when independent verification or coverage requires them. Do not select a provider only because this file names it.

## Provider tool sets

A provider selection includes its complete tool set. Evidence collection has discovery and retrieval operations. Discovery finds candidates. Retrieval reads a page before you cite it. Use both operations from the same provider when possible. A search snippet is discovery, not inspection. `ground-check` reports citations that do not have retrieval evidence.

| Provider (example) | Discovery | Retrieval (what you cite from) | Coverage / extras |
| --- | --- | --- | --- |
| Context7 | `resolve-library-id` | `query-docs` (version-scoped) | Resolve only when the library id is ambiguous |
| Tavily | `tavily_search` (topic, day/date filters) | `tavily_extract` | Crawl/map for broad section coverage; research for a public-web report |
| Exa | `search` | `contents` | `find_similar` widens a thin result set |
| Native web | web search | web fetch/open | — |
| Hallouminate | `ground` | `read_markdown` (cite path + lines) | `backlinks`, `list_tree` for neighbouring decisions |
| Git hosting (`gh`) | `gh search` (code/issues/prs) | `gh api`, `gh <noun> view` | Release/tag metadata for freshness claims |
| Local code intelligence | shared [routing contract](../../cheese/references/code-intelligence-routing.md) search | bounded read at the cited `file:line` | Dependency inspection for callers |

Rules:

- **Do not use a generic wrapper without a clear need.** Use the selected provider retrieval tool when it is available. Otherwise, record the substitution as `unavailable.md` specifies.
- **Record the provider and tool for every call.** Use the capture manifest in `context-isolation.md` § Capture manifest. A provider name does not prove that its retrieval tool read a page.
- **Treat discovery-only execution as committed-but-skipped.** Apply this status to claims that require page content.

## Provider-selected methods

### Library/API documentation

Ask one focused question that includes the version. Resolve the library only when the documentation index requires it. Then query the index. If the index is absent or incomplete, read an authoritative source. Sources include vendor documentation, `llms.txt`, package documentation, and the repository README.

Do not use a documentation provider for private application logic or repository architecture. It can also omit a new behavior. Route these parts to local code, repository knowledge, release notes, or the current web.

### Current-web discovery and extraction

Use a durable two-step pattern:

1. **Discover** authoritative candidate URLs with the selected search provider.
2. **Extract or open** only the strongest candidates. Use the same provider or a compatible fetcher. Focus on the claim under review.

Examples include Tavily search with extract, Exa search with contents, and native web search with open. For a large site, search or map its structure first. Then extract only the relevant pages. Crawl the site only when the question requires broad coverage. Deep research can support a comparative public web report. It does not replace repository knowledge or local code evidence.

Use provider date controls for freshness-sensitive facts when they are available. Record an absolute date. Use exact phrase search for literal errors or API names when possible. Filter candidates for authority and relevance before extraction.

### Repository knowledge/wiki

Query the configured repository knowledge source before you infer that a decision is absent. Suitable sources include Hallouminate, llm-wiki, and limited Markdown ADR or wiki reads. Cite the wiki or ADR path and relevant lines when possible.

### Local code intelligence

Use semantic search, structural search, limited reads, and dependency inspection through the shared contract. Local code defines current repository behavior. Repository knowledge defines recorded rationale. Route both capabilities when the question asks why the current code has its structure.

### Git hosting/examples

Use host-native search for repository metadata and code examples when it is available. Otherwise, use a host integration or host-specific web search. Separate maintained upstream state from third-party examples. Do not treat example frequency as proof of correctness.

## Source priority

Authority depends on the claim type:

1. **Current checkout behavior and conventions:** repo-local code wins. External docs describe an upstream contract; they do not override what this checkout does.
2. **Recorded repository decisions and rationale:** repository knowledge/ADRs win.
3. **External library/API configuration and migration claims:** official vendor/library docs win.
4. **Technical claims:** original papers, standards, and RFCs win.
5. **Version or freshness claims:** release notes, changelogs, and host metadata win.
6. **Real-world precedent:** Git-hosted examples support the claim but do not establish correctness.
7. **Coverage gaps:** blogs, tutorials, and AI-generated content are last resort and must be disclosed.

Run independent capabilities in parallel when the harness supports this work. Claim authority determines which evidence wins. Provider call order does not determine authority.

## Routing block

Emit this canonical block before fetching:

```text
ROUTING DECISION:
- Library/API documentation:      YES (provider: Context7; library/version: <scope>)
- Current-web discovery/extraction: YES (provider: native web; freshness: <window>)
- Repository knowledge/wiki:      NO  (no prior-decision question)
- Local code intelligence:        YES (provider: easy-cheese routing; local precedent matters)
- Git hosting/examples:           NO  (hosted state or examples not required)
SOURCE PRIORITY: checkout code for local behavior; vendor docs/releases for external API/freshness
```

Use `YES` or `NO` for each capability. Do this even when the answer is clear. The provider field can name any equivalent provider. It does not require a provider from the examples.

## Verify then cite

Use the selected provider retrieval operation to inspect each cited URL. Confirm that the source supports the claim. Tavily extract, Exa contents, and native web open are examples. If the provider cannot read the page, select one compatible fetcher. Record the substitution. The `synthesis.md` exemptions omit only link checks for user URLs and inline `file:line` references. They do not omit content inspection.

Record each retrieval in the capture manifest when it occurs. `ground-check` reads this manifest. It rejects each remote citation without a successful retrieval entry and tool name. This check compares citations with fetched sources, not memory.

## Hard rule

After collection, compare the routing block with the actual calls. Record evidence, an empty result, or an unavailable result for each `YES` capability. Include the selected fallback. Mark a capability without execution as **committed-but-skipped**. Report this gap. Apply the confidence rule from `synthesis.md`. Do not report a gap when an equivalent provider completes the capability.
