# Query planning

Choose planning depth before routing.

## Compact freshness plan

A single freshness-sensitive fact still needs a compact plan; do not skip planning merely because it has one answer.

```text
PLAN
- Fact: <single fact to verify>
- Fresh as of: <absolute date or window>
- Authority: <preferred primary source type>
- Done when: <authoritative current source answers it; independent check if stakes require>
```

Examples include the latest stable release, current maintainer, active support status, or a present vendor policy. Route only the capabilities needed to verify that fact.

## Full plan

Use the full plan when the question is multi-part, comparative, asks for the "best" option or best practice, or requests a report.

1. **Restate the decision being supported.** Name what the user will do with the evidence.
2. **Extract constraints.** Dates, versions, repository scope, languages, geographies, and deal-breakers become routing inputs.
3. **Clarify only if it changes the capability plan.** Ask at most one question.
4. **Decompose into 2-5 focused subqueries.** Each should be answerable from a coherent source set.
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

Apply these rules with whichever provider was selected:

- Keep discovery queries focused; do not send the whole report prompt as one search.
- Decompose once and fan independent subqueries out in one assistant turn where supported. Re-search only thin subqueries.
- Include decision-relevant constraints such as version, date, company, language, or repository.
- Apply freshness windows and authority/domain filters at the provider when available.
- Request snippets for discovery, then extract/open only the strongest URLs. Avoid pulling raw bodies for every result.
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

## When no visible plan is needed

Skip a visible plan only for a stable, single-source lookup whose scope and authority are already explicit, or a direct local file question that should not have triggered `/briesearch`. Questions the user already decomposed may reuse that decomposition, but still state freshness and stop criteria when current facts are involved.
