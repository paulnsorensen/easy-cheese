# Capability routing

Decide once which research capabilities will run, then commit. Every capability marked `YES` must execute through its selected provider, an explicit fallback, or a surfaced unavailable/empty result.

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
| Library/API documentation | APIs, configuration, migration guidance, supported versions | Prefer the native documentation helper. Otherwise use one authoritative equivalent such as Context7, official docs/`llms.txt`, or package docs. |
| Current-web discovery/extraction | Current facts, announcements, recent maintenance signals, locating and reading public pages | Prefer the native web backend. Otherwise use one search/extract pair such as Tavily or Exa. |
| Repository knowledge/wiki | Prior decisions, rationale, ADRs, conventions recorded as prose | Prefer the repository's configured wiki backend; examples include Hallouminate, llm-wiki, or bounded Markdown ADR/wiki reads. |
| Local code intelligence | Existing usage, implementations, local constraints | Follow the [shared source-code routing contract](../../cheese/references/code-intelligence-routing.md). |
| Git hosting/examples | Issues, releases, commits, pull requests, and OSS usage patterns | Use `gh`, a host integration, or host-scoped web discovery. Treat examples as supporting evidence unless precedent is the question. |

Prefer native easy-cheese helpers/backends when present. Otherwise select one equivalent provider per capability. Use multiple providers for one capability only when independent verification or coverage requires it, not because a named service appears in this document.

## Provider tool sets

Selecting a provider selects its **whole** tool set. Evidence-gathering splits into two operations, and a provider that ships both must be used for both: discovery locates candidates, retrieval reads the page you are about to cite. A search snippet is discovery, never inspection — citing a URL you only saw in a result list is the failure `ground-check`'s REMOTE rule exists to catch.

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

- **Do not degrade to a lowest-common-denominator wrapper.** When the selected provider ships its own retrieval tool, a generic fetcher is a substitution: use the provider's tool, or record the substitution per `unavailable.md`.
- **Record the provider *and* the tool** for every call in the capture manifest (`context-isolation.md` § Capture manifest). "Tavily" is not evidence that a page was read; `tavily_extract` on that URL is.
- **A capability marked `YES` whose only execution was discovery is committed-but-skipped** for any claim that needed the page content.

## Provider-selected methods

### Library/API documentation

Ask a focused, version-aware question. If a documentation index is available, resolve the library only when needed, then query it. If it is absent or incomplete, read official vendor documentation, `llms.txt`/`llms-full.txt`, package docs, or the repository README.

A documentation provider is unsuitable when the question concerns private application logic, repository-specific architecture, or a just-released behavior its indexed material does not cover. Route those parts to local code, repository knowledge, release notes, or current web instead.

### Current-web discovery and extraction

Use a durable two-step pattern:

1. **Discover** authoritative candidate URLs with the selected search provider.
2. **Extract or open** only the strongest candidates with the same provider or a compatible fetcher, focused on the claim being checked.

Examples: Tavily search then extract, Exa search then contents, or native web search then open. For a large site, map/search its structure before extracting a few relevant pages; crawl only when broad section coverage is required. A deep-research operation may serve a public-web comparative/report question, but it does not replace repository knowledge or local code evidence.

For freshness-sensitive facts, apply the provider's date/window controls when available and record an absolute as-of date. For literal errors or API names, use exact-phrase search when supported. Filter for authority and relevance before extraction.

### Repository knowledge/wiki

Query the repository's configured knowledge source before treating absence from code as absence of a decision. Hallouminate `ground`, llm-wiki queries, and targeted reads of Markdown ADR/wiki files are equivalent provider shapes. Cite the returned wiki/ADR path and relevant lines when possible.

### Local code intelligence

Use semantic/structural search, bounded reads, and dependency inspection through the shared routing contract. Local code is authoritative for current repository behavior; repository knowledge is authoritative for recorded rationale. Route both when the question asks why the current code has its shape.

### Git hosting/examples

Use host-native search for repository metadata and code examples when available. Fall back to a host integration or web search scoped to the host. Distinguish maintained upstream state from third-party examples, and do not treat example frequency as correctness.

## Source priority

Authority depends on the claim type:

1. **Current checkout behavior and conventions:** repo-local code wins. External docs describe an upstream contract; they do not override what this checkout does.
2. **Recorded repository decisions and rationale:** repository knowledge/ADRs win.
3. **External library/API configuration and migration claims:** official vendor/library docs win.
4. **Technical claims:** original papers, standards, and RFCs win.
5. **Version or freshness claims:** release notes, changelogs, and host metadata win.
6. **Real-world precedent:** Git-hosted examples support the claim but do not establish correctness.
7. **Coverage gaps:** blogs, tutorials, and AI-generated content are last resort and must be disclosed.

Run independent routed capabilities in parallel when the harness supports it. Claim-scoped authority governs which evidence wins, not a mandatory provider call order.

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

Use `YES` or `NO` for every capability even when the answer is obvious. The provider detail may name any selected equivalent; it does not require the examples above.

## Verify then cite

Confirm that each cited URL covers the claim with the selected provider's extraction/open/fetch operation. Tavily extract, Exa contents, and native web open are examples. If the selected search provider cannot read the page, use one compatible fetcher and record the substitution. The exemptions in `synthesis.md` waive only link-resolution checks for user-supplied URLs and inline `file:line` references; they never waive content inspection.

Record each retrieval in the capture manifest as it happens. `ground-check` reads that manifest and fails any cited `http(s)` URL with no successful retrieval entry naming the tool that opened it — so a deep report's citations are checked against what the run actually fetched, not against the model's memory of fetching.

## Hard rule

After gather, reconcile the routing block against execution. For each capability marked `YES`, record evidence, an empty result, or an unavailable result with the chosen fallback. A committed capability with no execution is **committed-but-skipped**: flag the gap and apply the confidence rule from `synthesis.md`. A missing named provider is not a gap when an evidence-equivalent provider completed the capability.
