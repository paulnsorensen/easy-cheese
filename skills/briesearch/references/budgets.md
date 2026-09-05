# Search budgets

A research run stops when new evidence does not change the answer. It does not stop only because the provider stops answering. Repeat calls cost time and provider quota. They do not add a claim. Declare the expected cost. Record the actual cost in the ledger.

## Declare the budget

Add a `budget` object to `manifest.json` (shape and fields: `context-isolation.md` § Capture manifest) before the first provider call:

```json
{"budget": {"search": 6, "extract": 8, "spawn": 1}}
```

Use these values as starting points, not as rules. A compact freshness check needs fewer calls. A comparative report needs more calls.

| Question shape | search | extract |
| --- | --- | --- |
| One freshness-sensitive fact | 2 | 2 |
| Single-subject "how does X work" | 4 | 5 |
| Comparative / best-practice report | 8 | 10 |

Declare a limit for each call kind that the run uses. `budget-check` reports `BUDGET_UNDECLARED` for a used kind with no limit. The budget is soft. You can exceed it only when you record the overspend.

## Extensions

To spend past the budget, append the evidence gap that forces it:

```json
{"extensions": [{"gap": "unresolved-contradiction", "note": "docs and changelog disagree on the default"}]}
```

`gap` MUST be one of these five values. A request for more sources is not a gap:

- `no-primary-source` — every hit so far is secondary or derivative.
- `unresolved-contradiction` — two credible sources disagree on a decision-critical fact.
- `missing-freshness` — no source is recent enough for a version-sensitive claim.
- `unanswered-question` — a planned sub-question has no evidence at all.
- `unsupported-claim` — a drafted claim has no citation that survives checking.

An extension names the gap that the extra calls must close. If the calls do not close it, report this result. Add the result to the open questions block. Do not spend more calls.

## Do not repeat calls

- **Same search twice.** The provider, query, and filters identify a search. Do not issue the same search again. Change the words only when you target a different sub-question.
- **Same URL twice.** Extract a canonical URL once. Then read the stored body. See `context-isolation.md` § Re-extraction in later turns. When freshness becomes relevant, fetch the URL again. Record `"refresh": true` for that fetch.
- **Failed calls.** Record the actual status and omit `file`. Do not use data from a failed retrieval as evidence.
- **Cached records.** Set `"cached": true` for an entry that an earlier run supplies. A cached record does not spend the call budget. `budget-check` reports it under `cached`.

## Check it

```bash
python3 skills/briesearch/scripts/briesearch.pyz budget-check <research-dir>
```

The command prints the run metrics to stdout. The metrics include invocation class, counts, spent counts, duplicates, cache hits, and failures. The command fails on `DUPLICATE_SEARCH`, `DUPLICATE_EXTRACT`, `FAILED_EVIDENCE`, `EXTENSION_GAP`, `BUDGET_UNDECLARED`, or `BUDGET`. `EXTENSION_GAP` identifies a value outside the five allowed values. `BUDGET_UNDECLARED` identifies a used call kind with no declared limit. `BUDGET` identifies overspend without a recognized extension. Run this command with `ground-check` before you finish a deep report.
