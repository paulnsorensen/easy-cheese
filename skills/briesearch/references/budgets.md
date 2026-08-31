# Search budgets

A research run stops when the evidence stops changing the answer, not when the provider stops answering. Repeat calls cost wall-clock time and provider quota while adding no claim, so the run declares what it expects to spend and the ledger records what it actually spent.

## Declare the budget

Add a `budget` object to `manifest.json` (shape and fields: `context-isolation.md` § Capture manifest) before the first provider call:

```json
{"budget": {"search": 6, "extract": 8, "spawn": 1}}
```

Starting points, not laws — a compact freshness check needs far less, a comparative report more:

| Question shape | search | extract |
| --- | --- | --- |
| One freshness-sensitive fact | 2 | 2 |
| Single-subject "how does X work" | 4 | 5 |
| Comparative / best-practice report | 8 | 10 |

The budget is soft: exceeding it is allowed, unrecorded overspend is not.

## Extensions

To spend past the budget, append the evidence gap that forces it:

```json
{"extensions": [{"gap": "unresolved-contradiction", "note": "docs and changelog disagree on the default"}]}
```

`gap` MUST be one of five, because "I want more sources" is not a gap:

- `no-primary-source` — every hit so far is secondary or derivative.
- `unresolved-contradiction` — two credible sources disagree on a decision-critical fact.
- `missing-freshness` — no source is recent enough for a version-sensitive claim.
- `unanswered-question` — a planned sub-question has no evidence at all.
- `unsupported-claim` — a drafted claim has no citation that survives checking.

An extension names the gap that the extra calls are meant to close. If those calls do not close it, say so in the open questions block rather than spending again.

## Don't repeat yourself

- **Same search twice.** Provider, query, and filters together are the identity of a search; re-issuing them returns the same answer. Reword only when the rewording targets a different sub-question.
- **Same URL twice.** Extract a canonical URL once and read the stored body afterwards (`context-isolation.md` § Re-extraction in later turns). When freshness genuinely became part of the question, re-fetch and record `"refresh": true`.
- **Failed calls.** Record the real status and no `file`. Debris from a failed retrieval is not evidence.

## Check it

```bash
python3 skills/briesearch/scripts/briesearch.pyz budget-check <research-dir>
```

Prints the run metrics — invocation class, per-kind counts, duplicates, cache hits, failures — on stdout, and fails on `DUPLICATE_SEARCH`, `DUPLICATE_EXTRACT`, `FAILED_EVIDENCE`, `EXTENSION_GAP` (a gap outside the five), or `BUDGET` (overspend with no recognised extension). Run it beside `ground-check` before finalizing a deep report.
