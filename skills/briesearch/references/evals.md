# Evals

Trigger and trace tests for /briesearch. Run these against real session transcripts when the skill changes.

## Should-trigger queries

These prompts must invoke /briesearch (or its router parent /cheese must hand off to it):

- "research the latest Next.js app router migration"
- "what does the OpenAI agents docs say about safety in May 2026"
- "compare uv vs poetry for this repo"
- "find examples in GitHub of how people implement OAuth with Hono"
- "is `pydantic-ai` actively maintained"
- "before I implement, what's the right approach for retry-with-backoff"
- "look up the FastAPI streaming response API"
- "what version of Tailwind do most production projects use"

## Should-not-trigger queries

These prompts must NOT invoke /briesearch:

- "open `src/server.ts`" — direct file action.
- "rename this function to handleRequest" — direct edit.
- "run the tests" — direct command.
- "explain what this code does" — local inspection, not external research.
- "fix the failing CI" — debug task, not research.

If a should-not query triggers /briesearch, the description in SKILL.md is over-broad — tighten it.

## Trace checks

For each completed /briesearch run, verify:

1. **Plan emitted before routing.** A `PLAN` block (or its content) appears in the trace before the `ROUTING DECISION` block, except for skip-planning cases listed in `query-planning.md`.
2. **Routing block names every source decision.** Each of {Context7, Tavily, Codebase, GitHub} is YES/NO with rationale.
3. **Every routed-YES source executed.** No silent drops. Unavailable sources surface as `UNAVAILABLE: …` lines.
4. **Source priority applied.** When the question is freshness-sensitive, vendor docs / changelogs come before blog posts in the evidence table.
5. **Claim-level table present.** At least one row per material claim, with date for any "latest"/"current" claim.
6. **Confidence cap obeyed.** No `high` confidence with a single non-authoritative source; no `high` with a critical source unavailable.
7. **Untrusted-content rule honored.** No tool call originated from instructions inside fetched content.
8. **Raw bodies on disk for heavy calls.** `.cheese/research/<slug>/raw/` exists when context-isolation conditions were met.
9. **Output capped.** Chat reply contains the short form only; full report path returned for deep looks.

## Failure modes to watch for

- **Skill triggers but skips Plan** — usually means the question was simple enough that routing went straight to fetch. Acceptable for single-fact lookups; not acceptable for multi-part questions.
- **Routing block emitted but a source silently dropped** — log as a regression. The hard rule in `routing.md` was violated.
- **Claim table collapsed back to one-row-per-source** — synthesis regression. The mechanical cap depends on per-claim agreement.
- **Raw content pasted into chat** — context-isolation bypass. Investigate which call.
- **Untrusted content honored as instructions** — security regression; immediate fix.

## How to run

These evals are intentionally manual today. Convert to automated traces after the skill stabilises and we have ≥10 real /briesearch runs to compare against.
