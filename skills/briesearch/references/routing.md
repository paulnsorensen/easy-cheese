# Source routing

Decide once which sources will run, then commit. If you commit a source in routing, you must execute it (or surface its unavailability) — never silently drop it.

## Decision tree

```
Is the question about a specific library API, config, or migration?
  YES → Context7  (+ GitHub if real-world usage matters)

Is it a factual / current / vendor / "what or who or when" question?
  YES → Tavily — see method matrix below

Is it "how should I…" or a best-practice question?
  YES → Tavily advanced  (+ Context7 when a named library is in scope)

Is it about patterns in this repo?
  YES → Codebase  (cheez-search + cheez-read)

Is it about how open-source projects solve something?
  YES → GitHub  (+ Tavily if written analysis would help)

Is it deep, multi-source, comparative, or "compare X vs Y / market analysis / lit review"?
  YES → Single tavily_research call (see "When to use tavily_research")
```

## Source guide

| Source | Best for | Notes |
| --- | --- | --- |
| Context7 (MCP) | Library APIs, config, migration notes for indexed open-source dependencies | Tools: `resolve-library-id` (`libraryName` + `query`) → `query-docs` (`libraryId` + `query`). Both require a `query`. See "Context7 method" below. |
| Tavily (MCP) | Current facts, technical articles, vendor docs, best practices, deep multi-source synthesis | Use the method matrix to pick the right rung. |
| Codebase | Local conventions, existing usage, constraints | Use `cheez-search` and `cheez-read`. |
| GitHub | Real-world OSS usage patterns | `gh` CLI or harness GitHub integration. Treat as supporting evidence unless the user asked for OSS precedent. |

## Context7 method

Two-step flow. Skip the first step (`resolve-library-id`) whenever an exact `/org/project` (or `/org/project/version`) ID is already known — supplied by the user or pasted into the prompt — which saves ~7K tokens per skip. Put the ID straight into the `query-docs` call and Context7 skips the matching step.

| Step | Tool | Args | Notes |
| --- | --- | --- | --- |
| 1 | `resolve-library-id` | `libraryName`, `query` | `query` is the user's full question, not just keywords — the server reranker uses it. |
| 2 | `query-docs` | `libraryId`, `query` | Pass the chosen `/org/project` from step 1, plus the same focused question. |

### Rules

- **Always pass a `query`.** Both tools rerank against it. A library name alone returns generic noise.
- **No `topic=` or `tokens=` parameters.** Modern Context7 reranks server-side (~3.3 K avg context tokens); the legacy `topic`/`tokens` knobs belong to the pre-rebrand `get-library-docs` and were removed. To narrow scope, write a richer `query` ("react hooks useState rules", "next.js 15 middleware auth").
- **Soft cap: ~3 Context7 calls per question.** Injected by the MCP tool description ("Do not call this tool more than 3 times per question"), not a documented upstream policy — the observed post-reranking average is ~2.96 calls. Beyond ~3, answer with the best result so far.
- **Cache library IDs within a session.** `/org/project` and `/org/project/version` are stable — once resolved, reuse without re-resolving. No expiry window is documented; handle 301 redirects (use the response's `redirectUrl`) and re-resolve per session to be safe.

### Error handling

- `"Documentation not found or not finalized"` → re-call `resolve-library-id` once with an alternate name (full vs short, scoped vs unscoped). If still empty, surface UNAVAILABLE per `unavailable.md` — do not retry the same ID.
- Multiple `resolve-library-id` matches → prefer the higher reputation / official org match; cite the chosen ID in the routing block.

### When Context7 comes up empty

If the library isn't indexed — or the question is about repo architecture, not API signatures — fall back in this order before generic web search (reach for whichever the harness actually has; the llms.txt path needs only WebFetch):

1. **llms.txt fast-path.** If the vendor publishes one (Anthropic, Vercel, Cloudflare, Stripe all do), `WebFetch` their `/llms.txt` (index) or `/llms-full.txt` directly — more authoritative than any crawl of the same docs.
2. **GitMCP** (`gitmcp.io`, free/OSS) — any public GitHub repo, zero pre-indexing, real-time; reads `llms.txt`/`llms-full.txt`/README first. Best for the long tail Context7 hasn't indexed.
3. **DeepWiki MCP** (`mcp.deepwiki.com`, free/no-auth for public repos; `ask_question`) — whole-repo architecture and "how does this fit together" questions Context7 can't answer (it returns API snippets, not narrative).

### When Context7 is the wrong tool

- Refactoring, business logic, debugging, code review, general programming concepts.
- Application code or internal libraries with no public docs.
- Niche packages absent from Context7's index (~110 K libraries as of mid-2026; the index grows on-demand — submit a repo via the web UI or POST llms.txt / OpenAPI specs to `/api/v2/add/llmstxt` / `/api/v2/add/openapi`, private repos on paid plans — so absence is fixable, not permanent).
- Mature, well-known libraries the model already covers reliably — value is marginal; skip to spare a routed call.

### Cost and freshness

- **Free tier is ~1,000 calls/month** (cut ~83% in Jan 2026 from ~6,000); Pro is $10/seat/month. High-frequency runs can drain the free tier — spend routed calls deliberately.
- **Private repos** need Pro (+ ~$25 / 1M tokens for private parsing) or Enterprise.
- **Freshness is tiered**: top-100 libraries refresh daily, top-1,000 ~every 15 days, top-5,000 ~every 30 days, the long tail up to ~45 days. For a just-released version the indexed docs can lag — cross-check the changelog before trusting them.

Upstream reference (canonical):

- <https://github.com/upstash/context7/blob/main/README.md>
- <https://github.com/upstash/context7/blob/main/rules/context7-mcp.md>

## Tavily method matrix

The Tavily MCP exposes 5 tools at increasing cost and precision. Pick the lowest rung that answers the question; escalate only when the previous rung returns nothing useful.

| Need | Tool | When |
| --- | --- | --- |
| Discover sources, snippets, scores; no URL yet | `tavily_search` | First reach for any factual / "what's the latest" question. Leave `include_raw_content=false`; pull bodies via `tavily_extract` instead. |
| Have URL(s), need clean markdown | `tavily_extract` | After search, or when the user supplies links. Up to 20 URLs per call. Pass `query=` so chunks rerank against the question. Set `extract_depth=advanced` for tables, embedded content, LinkedIn, or other protected sites. |
| Big site, don't know the right page | `tavily_map` | URL-only structure of a domain. Cheap. Pair with `tavily_extract` (Map-then-Extract) for surgical access to large docs sites. |
| Many pages on a site section (e.g. all `/docs/auth/*`) | `tavily_crawl` | Most expensive. Start with `max_depth=1`, use `select_paths` and semantic `instructions` to keep results on-topic. `extract_depth` applies here too: `basic` = 1 credit / 5 URLs, `advanced` = 2 / 5. |
| Multi-source synthesis with citations (compare X vs Y, market report, lit review) | `tavily_research` | Blocking — one call returns the cited report directly (params: `input`, `model`). 30-120s. Use `model=mini` for narrow scope, `pro` for multi-domain, `auto` if unsure. Rate limit: 20 req/min — fan out subqueries via `tavily_search`, not parallel research calls. |

### Search depth (when calling `tavily_search`)

| Depth | Latency | Relevance | Use when |
| --- | --- | --- | --- |
| `ultra-fast` | Lowest | Lower | Real-time UX (rare in /briesearch). |
| `fast` | Low | Good | Need chunks but latency matters. |
| `basic` | Medium | High | General-purpose default. |
| `advanced` | Higher | Highest | Specific information queries; precision matters. Follow with `tavily_extract(query=…)` on the top-scoring URLs. |

### Filters

- **Time**: **set `time_range` whenever the question carries "latest" / "current" / "newest" or names a year** (`day` / `week` / `month` / `year`) — omitting it on a freshness-sensitive question is the single most common miss. Use `start_date` / `end_date` for absolute windows.
- **Domain**: `include_domains=[...]` for trusted sources (vendor, arxiv.org, github.com); `exclude_domains=[...]` for noise (reddit.com, quora.com).
- **Score**: post-filter response items before extracting (the score is in the response, not a request param). Keep `score > 0.5` as the floor for extraction candidates; tighten to `score > 0.7` when you only want high-confidence sources.
- **Exact phrase**: `exact_match=true` when chasing a literal quote, error string, or API name.
- **`chunks_per_source`** (1-3 on search; 1-5 on extract/crawl): how many reranked snippets come back per source at `advanced`/`fast` depth. `1` trims context, `3` maximises coverage — a direct context-budget lever.
- **Avoid the `auto_parameters` cost trap**: `auto_parameters=true` lets Tavily auto-pick depth and may silently set `search_depth=advanced` (2 credits). Set `search_depth` explicitly when cost matters.
- **Post-filter beyond score**: score is the cheap first cut; for precision-sensitive questions also drop results by URL/term regex or a quick LLM "does this cover X?" check.

### Composite patterns

- **Search-then-Extract** (default two-step): `tavily_search` for discovery → drop results with `score ≤ 0.5` → `tavily_extract(urls=[…], query=<focused question>)` on the survivors. Cheaper and lower-noise than `include_raw_content=true` on search.
- **Map-then-Extract** (large docs sites): `tavily_map(url=…, select_paths=[…])` to find the 1-3 right URLs without paying for content → `tavily_extract` only those. Cheaper than `tavily_crawl` when you don't need every page.
- **Verify-then-cite** (link verification): to confirm a URL loads *and* actually covers the claimed topic, use `tavily_extract(urls=[…], query=<the claim>)` — its LLM-optimized clean content makes the "does this page cover X" judgment sharper and cheaper than raw HTML. This is the preferred verification/extraction primitive. WebFetch is the fallback, not the default — reach for it only when the Tavily MCP is unavailable (see `unavailable.md`).

### When to use `tavily_research`

A single MCP call beats hand-orchestrating search+extract when:

- The question is comparative ("X vs Y").
- The deliverable is a cited report, not a single fact.
- The scope is multi-domain (market analysis, competitive landscape, literature review).
- 30-120s latency is acceptable.

Hand-orchestrate (search → score-filter → extract → synthesize) instead when:

- The question is cross-source — Tavily plus Context7 plus codebase plus GitHub. `tavily_research` only sees public web; private signals require local synthesis.
- You need fine-grained control over which URLs feed synthesis.
- The user wants the raw evidence table, not a narrative report.

Upstream reference (canonical):

- <https://github.com/tavily-ai/skills/blob/main/skills/tavily-cli/SKILL.md>
- <https://github.com/tavily-ai/skills/tree/main/skills/tavily-best-practices/references>

## Source priority

Within each source class, prefer authoritative over secondary:

1. **Official vendor / library docs** for API, config, migration claims.
2. **Original papers, standards, RFCs** for technical claims.
3. **Release notes / changelogs** for version or freshness claims.
4. **Repo-local evidence** (cheez-search) for local conventions.
5. **GitHub examples** as supporting evidence unless the user asked for OSS precedent.
6. **Blogs, tutorials, AI-generated content** only when nothing above answers the question — and disclose them as such.

For named-library questions, the routed-call order is **cheez-search → Context7 → Tavily**: cheap repo precedent first, the library's own indexed docs second, current-events / vendor announcements / coverage gaps last. Fan all routed calls in a single assistant turn (parallel tool calls) so total wall time is one round-trip.

## Routing block

Emit the decision compactly before fetching:

```text
ROUTING DECISION:
- Context7: YES (library: "<library>", query: "<focused question>")
- Tavily:   YES (rung: search, depth: basic, filters: time_range=month)
- Codebase: YES (local precedent matters)
- GitHub:   NO  (not looking for OSS usage patterns)
SOURCE PRIORITY: vendor docs > release notes > repo precedent
```

## Hard rule

If a source was committed in routing, spawn it. If it returns "unavailable", report that — do not silently drop a routed source because it later seems low-value.

Make this mechanical, not honor-system. After gather, diff the emitted `ROUTING DECISION` against what actually ran: for each source marked `YES`, confirm a call executed and produced evidence, an `unavailable` result, or an empty result. Any committed source with no corresponding execution is **committed-but-skipped** — mark it explicitly in the report (a `Searched, empty` line if it ran dry, an UNAVAILABLE note per `unavailable.md` if it failed, or a flagged gap if it was simply not run) and apply the matching confidence cap from `synthesis.md`. A `YES` in the routing block with nothing to show for it is a reconciliation failure, not a silent drop.
