# Query planning

Run this before routing. The goal is to know what answer would close the question, not to get an answer immediately.

## Five steps

1. **Restate the decision being supported.** What action does the user take after this research? Different deliverables (decision, spec input, code change) call for different sources.
2. **Extract constraints.** Dates, versions, repo scope, languages, geographies, deal-breakers. These become filters in the routing block.
3. **Clarify only if it changes the source plan.** Ask at most one question, and only when missing context would route to a different source set. "Which version of Next.js?" — yes if Next.js routing differs by major. "What's your deadline?" — no, doesn't change sources.
4. **Decompose into 2-5 focused subqueries.** Multi-faceted questions ("competitive landscape of X") fan out badly when sent as one query. Each subquery should be a thing a search engine could answer in one page.
5. **Name stop criteria.** Before fetching, write down what "done" looks like: "two authoritative sources agree", "vendor docs explicitly answer the API question", "no source contradicts the claim within last 3 months". Stop when met; don't keep gathering.

## Tavily query construction

Pulled from `tavily-best-practices/references/search.md`
(<https://github.com/tavily-ai/skills/blob/main/skills/tavily-best-practices/references/search.md>):

- **Keep queries under 400 characters.** Short query, not a long-form prompt.
- **Don't compose one giant query** — break it into the 2-5 subqueries from step 4 and run them in parallel. In the Claude Code harness, parallelism means a single assistant turn with multiple tool calls; sequential turns serialise.
- **Include constraints in the query**: company names, framework versions, geographies, year. Search engines reward concrete keywords.
- **Pick the right depth**: `basic` for general lookups (default), `advanced` for precision-sensitive questions, `fast` when latency matters.
- **Filter freshness at the API**, not after: `time_range="month"` for current facts, `start_date`/`end_date` for absolute windows.
- **Filter authority at the API**: `include_domains=["arxiv.org","github.com","sec.gov"]` for trusted sources, `exclude_domains=["reddit.com","quora.com"]` for noise.
- **Don't ask `tavily_search` for raw bodies.** Leave `include_raw_content=false`; pass the surviving URLs to `tavily_extract(query=…)` instead. Cheaper, lower noise, and aligns with `context-isolation.md`.

## Subquery decomposition examples

Bad (one big query):

> "competitive landscape of AI code assistants in 2026 including market share, pricing, key differentiators, customer segments, and recent product moves"

Good (5 focused subqueries):

1. "AI code assistant market share 2026"
2. "Cursor vs GitHub Copilot vs Claude Code pricing 2026"
3. "AI code assistant key differentiators 2026"
4. "AI code assistant enterprise customer segments 2026"
5. "Cursor product launches 2026" / "Copilot product launches 2026" / "Claude Code product launches 2026"

Run them in parallel, score-filter, then extract the top URLs per subquery.

## Stop criteria template

Pin down before routing:

```text
PLAN
- Decision: <what the user does next>
- Constraints: <versions, dates, scope, language>
- Subqueries: 1) <q1>  2) <q2>  3) <q3>
- Done when: <concrete signal>
- Source priority: <vendor docs > … > GitHub examples>
```

The routing block (in `routing.md`) consumes this directly.

## When to skip planning

A planning step that's longer than the answer wastes context. Skip the full Plan emission for:

- Single-fact lookups ("what's the latest stable Node version").
- Single-file local questions ("where does this repo wire up auth").
- Questions the user has already decomposed.

Always plan when:

- The question has more than one moving part (X and Y, before/after, multiple criteria).
- The question is comparative.
- "Latest", "current", or "best" is in the question.
- The deliverable is a report rather than a fact.
