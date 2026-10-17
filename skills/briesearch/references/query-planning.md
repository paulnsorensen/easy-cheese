# Query planning

Choose planning depth before routing.

## Compact freshness plan

A single freshness-sensitive fact still needs a compact plan. Do not skip the plan because the fact has one answer.

```text
PLAN
- Fact: <single fact to verify>
- Fresh as of: <absolute date or window>
- Authority: <preferred primary source type>
- Done when: <authoritative current source answers it; independent check if stakes require>
```

Examples include the latest stable release, current maintainer, active support status, or a present vendor policy. Route only the capabilities needed to verify that fact.

## Full plan

Use the full plan for a multi-part question, a comparison, a best-practice question, or a report.

1. **Restate the supported decision.** Name what the user will do with the evidence.
2. **Extract constraints.** Use dates, versions, repository scope, languages, geographies, and deal-breakers as routing inputs.
3. **Clarify only if it changes the capability plan.** Ask at most one question.
4. **Decompose the question into 2-5 focused subqueries.** One coherent source set must answer each subquery.
5. **Name stop criteria.** Define the evidence that makes the research complete.

```text
PLAN
- Decision: <what the user does next>
- Constraints: <versions, dates, scope, language>
- Subqueries: 1) <q1>  2) <q2>  3) <q3>
- Done when: <concrete evidence signal>
- Source priority: <vendor docs > repository knowledge > local code > examples>
```

## Query construction

Apply these rules with the selected provider:

- Keep each discovery query focused. Do not send the complete report prompt as one search.
- Decompose the question once. Send the independent subqueries in one turn when the harness supports parallel work. Search again only for a thin subquery.
- Include decision-relevant constraints such as version, date, company, language, or repository.
- Apply freshness windows and authority/domain filters at the provider when available.
- Request snippets for discovery. Then open only the strongest URLs. Do not retrieve a raw body for every result.
- Use exact-phrase matching for literal errors, quotes, or API names when supported.

Examples: Tavily search filters, Exa category/domain/date controls, and native web recency/domain filters are different interfaces for the same planning decisions.

## Decomposition example

Bad:

> "compare two API clients for this repository, including compatibility, maintenance, migration cost, and current adoption"

Better:

1. Official compatibility and supported-version claims for each client.
2. Current release/maintenance signals.
3. Existing repository usage and constraints.
4. Hosted examples from comparable projects.
5. Migration differences that affect the stated decision criteria.

Run independent subqueries in parallel, then extract the strongest evidence per claim.

## When you can omit a visible plan

Skip a visible plan only for a stable lookup with one clear source, scope, and authority. Also skip it for a direct local file question. Such a question must not trigger `/briesearch`. Reuse a decomposition that the user supplies. State the freshness window and the stop criteria for a current fact.
