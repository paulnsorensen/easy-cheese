# Context isolation

A large discovery or extraction result can consume the main context window. Keep raw bodies on disk. Surface only the evidence that the synthesis needs.

## When to apply

Apply context isolation when a selected provider operation is likely to return many full bodies or a large synthesized report:

- Search with raw/full content enabled or a broad result set.
- Multi-URL extraction or content retrieval.
- Site crawl/map followed by broad extraction.
- Deep research or report operations that must retain their sources.
- Any response likely to crowd out the routing plan and claim table.

Provider examples include Tavily crawl or research, Exa contents, and batches of native web opens. Skip isolation for snippet triage. Also skip it for a small set of focused page reads.

## The recipe

1. **Generate a slug.** Use 4-6 kebab-case words derived from the question. `synthesis.md` states the same limit.
2. **Resolve the layout.** Run `python3 skills/briesearch/scripts/briesearch.pyz research-layout <slug>`. The command prints the `dir`, `report`, `raw_dir`, and `manifest` absolute paths. It also prints the corpus-relative `artifact` path. Use these paths without changes. Do not derive them again. The command rejects a slug outside the four-to-six-word range.
3. **Run the heavy provider operation in a separate sub-agent.** Do not run it in the main context. Give the routing block and the layout's `corpus_root` to the sub-agent.
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

   The manifest is the run ledger. See `## Capture manifest`. Write each call when it occurs. Do not write calls from memory at the end.

5. **Filter inside the sub-agent.** Apply the required relevance checks. Build the claim rows from `synthesis.md`. Bind each Freshness value to the manifest fetch date. Use `"live"` for an unstored live check.
6. **Return auditable pointers.** Return the short claim table, confidence, gaps, and report path. Each stored claim cites `raw/NN-<host>.md#Lstart-end`. Keep raw bodies on disk.

## Capture manifest

`ground-check` and `budget-check` read `manifest.json`. Use this fixed shape:

```json
{
  "slug": "hybrid-retrieval-fusion",
  "invocation": "top-level",
  "budget": {"search": 6, "extract": 8, "spawn": 1},
  "extensions": [],
  "calls": [
    {"kind": "search", "provider": "tavily", "tool": "tavily_search",
     "query": "reciprocal rank fusion k", "filters": {"days": 30}, "status": "ok"},
    {"kind": "extract", "provider": "tavily", "tool": "tavily_extract",
     "url": "https://example.com/rrf",
     "url_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
     "file": "raw/01-example.md", "title": "RRF",
     "fetched": "2026-08-30", "status": "ok"},
    {"kind": "spawn", "provider": "researcher", "status": "ok"}
  ]
}
```
- For an `extract` call, use `url` only as a display value. Keep the scheme, host, and path. Omit user information, query values, and fragments. Record `url_digest` as the lowercase SHA-256 digest of the full canonical URL before redaction. Never write a credential-bearing raw URL to the manifest or a report.

- `kind` is `search`, `extract`, or `spawn`. `invocation` is `top-level` when the user asks. It is `sidechain` when another skill asks.
- Record `provider` and `tool` for each search and extraction. These fields identify the provider tool that read the page. A search result does not prove this. See `routing.md` § Provider tool sets.
- `status` defaults to `ok`. Record each failure with its actual status. Omit `file` for a failure. A failed fetch is not evidence. `ground-check` rejects citations that use a failed fetch.
- Set `"refresh": true` when you extract a ledger URL again for freshness. Set `"cached": true` when an earlier run entry supplies the call.
- Declare `budget` before the first provider call. Add an `extensions` entry before you exceed that budget. See `budgets.md`.

## Re-extraction in later turns

For a follow-up that needs more detail:

- Read the manifest to locate the stored body.
- Read that body and extract the new claim.
- Append a claim row and update the report.
- Do not call any provider again for the same stored URL unless freshness is now part of the question.

## Out of git

The durable corpus lives outside the repo checkout (default `~/.local/share/cheese/<project>/`), so raw bodies never enter git.

## Do not treat this process as caching

Do not reuse raw bodies from another slug without a relevance check. The evidence filter is specific to each question.
