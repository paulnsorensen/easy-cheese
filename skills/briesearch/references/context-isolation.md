# Context isolation

High-volume search/extract output destroys the main context window if it lands in chat. Keep raw bodies on disk; surface only the signal.

Adapted from Tavily's `tavily-dynamic-search` (Programmatic Tool Calling pattern):
<https://github.com/tavily-ai/skills/blob/main/skills/tavily-dynamic-search/SKILL.md>

## Why this matters

A single `tavily_search` with `include_raw_content=true` returns ~5-20 results × ~30-50 K chars each. That's 150K-1M characters of mostly boilerplate (nav, footer, cookies, ads).

The fix: raw bodies stay on disk. Only the curated evidence table reaches the caller. Preferring `tavily_extract` over raw WebFetch at the verify/extract step shrinks that on-disk volume further: its LLM-optimized clean content carries far less boilerplate per result than raw HTML, so `research/<slug>/raw/` stays smaller and sharper.

## When to apply

Apply context isolation whenever a routed call is **heavy**:

- `tavily_search` with `include_raw_content=true`.
- `tavily_search` with `max_results > 10`.
- `tavily_extract` with more than 3 URLs.
- Any `tavily_crawl` call.
- Any `tavily_research` call where you also want the raw sources kept.

Skip it for triage searches (snippets only, ≤10 results) and single-URL extracts.

## The recipe

1. **Generate a slug.** 4-6 kebab-case words derived from the question. Same slug as `synthesis.md` uses for the report.
2. **Resolve the durable corpus root.** `ROOT=$(python3 ${CLAUDE_SKILL_DIR}/scripts/briesearch.pyz artifact-path research <slug>)` — the per-project durable corpus (see `../shared/formatting.md` § Corpus location). All paths below are composed under `"$ROOT/research/<slug>/"`.
3. **Run the heavy call from a forked sub-agent**, not from the main context. The sub-agent receives the routing block and `$ROOT`, and writes raw bodies to `"$ROOT/research/<slug>/raw/"`.
4. **Persist raw bodies as files.** One file per result/URL:

   ```
   $ROOT/research/<slug>/
   ├── raw/
   │   ├── 01-<host>.md         # tavily_search result body
   │   ├── 02-<host>.md
   │   └── …
   ├── manifest.json             # {url, title, score, fetch_date} per file
   └── <slug>.md                 # the human-readable report
   ```

5. **Filter inside the sub-agent.** Score threshold, paragraph keyword match, regex on body — whatever the question demands. Build the claim-level rows from `synthesis.md`. **Bind the Freshness column to `manifest.json`, not free text:** each row's Freshness is the `fetch_date` of the raw file the claim cites (or `"live"` for an unstored live check), so the column can't drift from what was actually fetched.
6. **Return the synthesis with auditable pointers.** The sub-agent's reply to the parent contains: the short-form output (claim table + confidence + path), nothing else. **Every claim row's Evidence cell must cite an on-disk raw pointer** — `raw/NN-<host>.md#Lstart-end` — so the parent (or a later turn) can spot-check the claim→evidence binding without re-fetching. A row whose evidence is not traceable to a stored raw body does not ship. Raw bodies stay on disk for re-extraction in later turns.

## Re-extraction in later turns

If the user asks a follow-up that needs more detail from a result you stored:

- Read `"$ROOT/research/<slug>/manifest.json"` to find the right file.
- Read the specific raw body and extract the new claim.
- Append a new row to the claim table; bump the report file.
- Do not re-call Tavily for the same URL — it is already on disk.

## Out of git

The durable corpus lives outside the repo checkout (default `~/.local/share/cheese/<project>/`), so raw bodies never enter git.

## Don't mistake this for caching

Don't reuse another slug's `research/<other-slug>/raw/` for a different question — the relevance filter is question-specific.
