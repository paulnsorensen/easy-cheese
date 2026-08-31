# Context isolation

High-volume discovery/extraction output can consume the main context window. Keep raw bodies on disk; surface only the evidence needed for synthesis.

## When to apply

Apply context isolation when a selected provider operation is likely to return many full bodies or a large synthesized report:

- Search with raw/full content enabled or a broad result set.
- Multi-URL extraction or content retrieval.
- Site crawl/map followed by broad extraction.
- Deep-research/report operations whose underlying sources must be retained.
- Any response likely to crowd out the routing plan and claim table.

Provider examples include Tavily crawl/research, Exa contents over many URLs, and batches of native web opens. Skip isolation for snippet-only triage and a small number of focused page reads.

## The recipe

1. **Generate a slug.** Use 4-6 kebab-case words derived from the question, matching `synthesis.md`.
2. **Resolve the layout.** `python3 skills/briesearch/scripts/briesearch.pyz research-layout <slug>` prints the JSON paths (`dir`, `report`, `raw_dir`, `manifest`) for this slug. Use them verbatim; do not re-derive them.
3. **Run the heavy provider operation from a forked sub-agent**, not the main context. Give it the routing block and `$ROOT`.
4. **Persist raw bodies as files.** One file per result/URL:

   ```text
   $ROOT/research/<slug>/
   ├── raw/
   │   ├── 01-<host>.md
   │   ├── 02-<host>.md
   │   └── …
   ├── manifest.json
   └── <slug>.md
   ```

   The manifest is the run ledger — see `## Capture manifest` below. Write it as calls happen, not from memory at the end.

5. **Filter inside the sub-agent.** Apply the relevance checks the question requires and build the claim-level rows from `synthesis.md`. Bind each Freshness value to the manifest fetch date (or `"live"` for an unstored live check).
6. **Return auditable pointers.** The sub-agent returns the short-form claim table, confidence, gaps, and report path. Each stored claim cites `raw/NN-<host>.md#Lstart-end`; raw bodies stay on disk.

## Capture manifest

`manifest.json` is machine-read by `ground-check`, so it has a fixed shape:

```json
{
  "slug": "hybrid-retrieval-fusion",
  "invocation": "top-level",
  "calls": [
    {"kind": "search", "provider": "tavily", "tool": "tavily_search",
     "query": "reciprocal rank fusion k", "filters": {"days": 30}, "status": "ok"},
    {"kind": "extract", "provider": "tavily", "tool": "tavily_extract",
     "url": "https://example.com/rrf", "file": "raw/01-example.md",
     "title": "RRF", "fetched": "2026-08-30", "status": "ok"},
    {"kind": "spawn", "provider": "researcher", "status": "ok"}
  ]
}
```

- `kind` is `search`, `extract`, or `spawn`. `invocation` is `top-level` (the user asked) or `sidechain` (another skill asked).
- `provider` and `tool` are both required for searches and extractions: which provider tool ran is the evidence that a page was read, not just listed (`routing.md` § Provider tool sets).
- `status` defaults to `ok`. Record failures with their real status and no `file` — a failed fetch is not evidence, and `ground-check` will not let it ground a citation.
- Set `"refresh": true` on a deliberate re-extraction of a URL already in the ledger (freshness is now part of the question), and `"cached": true` when a call was served from an earlier entry in this run.

## Re-extraction in later turns

For a follow-up that needs more detail:

- Read the manifest to locate the stored body.
- Read that body and extract the new claim.
- Append a claim row and update the report.
- Do not call any provider again for the same stored URL unless freshness is now part of the question.

## Out of git

The durable corpus lives outside the repo checkout (default `~/.local/share/cheese/<project>/`), so raw bodies never enter git.

## Don't mistake this for caching

Do not reuse another slug's raw bodies for a different question without rechecking relevance; the evidence filter is question-specific.
