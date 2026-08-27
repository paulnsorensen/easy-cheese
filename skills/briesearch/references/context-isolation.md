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
2. **Resolve the durable corpus root.** `ROOT=$(python3 skills/briesearch/scripts/briesearch.pyz artifact-path research <slug>)`. Compose paths under `"$ROOT/research/<slug>/"`.
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

   The manifest records the URL, title, selected provider, and fetch date for each file.

5. **Filter inside the sub-agent.** Apply the relevance checks the question requires and build the claim-level rows from `synthesis.md`. Bind each Freshness value to the manifest fetch date (or `"live"` for an unstored live check).
6. **Return auditable pointers.** The sub-agent returns the short-form claim table, confidence, gaps, and report path. Each stored claim cites `raw/NN-<host>.md#Lstart-end`; raw bodies stay on disk.

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
