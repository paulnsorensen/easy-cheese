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
| Context7 (MCP) | Library APIs, config, migration notes | Prefer over general web for any named dependency. |
| Tavily (MCP) | Current facts, technical articles, vendor docs, best practices, deep multi-source synthesis | Use the method matrix to pick the right rung. |
| Codebase | Local conventions, existing usage, constraints | Use `cheez-search` and `cheez-read`. |
| GitHub | Real-world OSS usage patterns | `gh` CLI or harness GitHub integration. Treat as supporting evidence unless the user asked for OSS precedent. |

## Tavily method matrix

The Tavily MCP exposes 5 tools at increasing cost and precision. Pick the lowest rung that answers the question; escalate only when the previous rung returns nothing useful.

| Need | Tool | When |
| --- | --- | --- |
| Discover sources, snippets, scores; no URL yet | `tavily_search` | First reach for any factual / "what's the latest" question. |
| Have URL(s), need clean markdown | `tavily_extract` | After search, or when the user supplies links. Up to 20 URLs per call. Pass `query=` + `chunks_per_source=3` to keep raw_content focused. |
| Big site, don't know the right page | `tavily_map` | URL-only structure of a domain. Cheap. Pair with `tavily_extract` (Map-then-Extract) for surgical access to large docs sites. |
| Many pages on a site section (e.g. all `/docs/auth/*`) | `tavily_crawl` | Most expensive. Start with `max_depth=1`, use `select_paths` and semantic `instructions` + `chunks_per_source=3`. |
| Multi-source synthesis with citations (compare X vs Y, market report, lit review) | `tavily_research` | One call returns a cited report. 30-120s. Use `model=mini` for narrow scope, `pro` for multi-domain, `auto` if unsure. |

### Search depth (when calling `tavily_search`)

| Depth | Latency | Relevance | Use when |
| --- | --- | --- | --- |
| `ultra-fast` | Lowest | Lower | Real-time UX (rare in /briesearch). |
| `fast` | Low | Good | Need chunks but latency matters. |
| `basic` | Medium | High | General-purpose default. |
| `advanced` | Higher | Highest | Specific information queries; precision matters. Pair with `chunks_per_source=5`. |

### Filters

- **Time**: `time_range` (`day` / `week` / `month` / `year`) for "latest" questions. Or `start_date` / `end_date` for absolute windows.
- **Domain**: `include_domains=[...]` for trusted sources (vendor, arxiv.org, github.com); `exclude_domains=[...]` for noise (reddit.com, quora.com).
- **Score**: post-filter results by `score > 0.5` before extracting.

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
