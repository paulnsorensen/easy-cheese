# Context isolation

High-volume search/extract output destroys the main context window if it lands in chat. Keep raw bodies on disk; surface only the signal.

Adapted from Tavily's `tavily-dynamic-search` (Programmatic Tool Calling pattern):
<https://github.com/tavily-ai/skills/blob/main/skills/tavily-dynamic-search/SKILL.md>

## Why this matters

A single `tavily_search` with `include_raw_content=true` returns ~5-20 results × ~30-50 K chars each. That's 150K-1M characters of mostly boilerplate (nav, footer, cookies, ads). If it enters chat, reasoning quality degrades and downstream calls burn tokens reading garbage.

The fix: raw bodies stay on disk. Only the curated evidence table reaches the caller.

## When to apply

Apply context isolation whenever a routed call is **heavy**:

- `tavily_search` with `include_raw_content=true`.
- `tavily_search` with `max_results > 10`.
- `tavily_extract` with more than 3 URLs.
- Any `tavily_crawl` call.
- Any `tavily_research` call where you also want the raw sources kept.

Skip it for triage searches (snippets only, ≤10 results) and single-URL extracts.

## The recipe

1. **Generate a slug.** 4-6 kebab-case words derived from the question. Same slug as `synthesis.md` uses for `.cheese/research/<slug>/<slug>.md`.
2. **Run the heavy call from a forked sub-agent**, not from the main context. The sub-agent receives the routing block and writes raw bodies to `.cheese/research/<slug>/raw/`.
3. **Persist raw bodies as files.** One file per result/URL:

   ```
   .cheese/research/<slug>/
   ├── raw/
   │   ├── 01-<host>.md         # tavily_search result body
   │   ├── 02-<host>.md
   │   └── …
   ├── manifest.json             # {url, title, score, fetch_date} per file
   └── <slug>.md                 # the human-readable report
   ```

4. **Filter inside the sub-agent.** Score threshold, paragraph keyword match, regex on body — whatever the question demands. Build the claim-level rows from `synthesis.md`.
5. **Return only the synthesis.** The sub-agent's reply to the parent contains: the short-form output (claim table + confidence + path), nothing else. Raw bodies stay on disk for re-extraction in later turns.

## Re-extraction in later turns

If the user asks a follow-up that needs more detail from a result you stored:

- Read `.cheese/research/<slug>/manifest.json` to find the right file.
- Read the specific raw body and extract the new claim.
- Append a new row to the claim table; bump the report file.
- Do not re-call Tavily for the same URL — it is already on disk.

## Gitignore

`.cheese/` is already gitignored project-wide. Raw bodies do not enter git.

## Don't mistake this for caching

This is **scoped to a single research question**. The slug ties raw bodies to a specific question's report. Don't reuse `.cheese/research/<other-slug>/raw/` for a different question — the relevance filter is question-specific.
