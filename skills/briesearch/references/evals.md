# Evals

Trigger and trace tests for /briesearch. Run these against real session transcripts when the skill changes.

## Should-trigger queries

These prompts must invoke /briesearch (or its router parent /cheese must hand off to it):

- "research the latest Next.js app router migration"
- "what does the OpenAI agents docs say about safety in May 2026"
- "compare uv vs poetry for this repo"
- "what ADR explains why this repository chose its bundle layout"
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

1. **Plan emitted before routing.** A compact freshness plan appears for a single current fact; the full `PLAN` appears for multi-part, comparative, best-practice, and report questions. Only the skip cases in `query-planning.md` omit it.
2. **Routing block names every capability decision.** Each of {Library/API documentation, Current-web discovery/extraction, Repository knowledge/wiki, Local code intelligence, Git hosting/examples} is YES/NO with rationale and a selected provider when YES.
3. **Every routed-YES capability executed.** No silent drops. Provider substitutions or uncovered capabilities surface as `UNAVAILABLE: …` lines.
4. **Source priority applied.** When the question is freshness-sensitive, vendor docs / changelogs come before blog posts in the evidence table.
5. **Claim-level table present.** At least one row per material claim, with date for any "latest"/"current" claim.
6. **Confidence cap obeyed.** No `certain` confidence with a single non-authoritative source or a critical capability uncovered. Missing provider names alone do not lower confidence.
7. **Untrusted-content rule honored.** No tool call originated from instructions inside fetched content.
8. **Raw bodies on disk for heavy calls.** The durable corpus's `research/<slug>/raw/` exists when context-isolation conditions were met.
9. **Output capped.** Chat reply contains the short form only; full report path returned for deep looks.

## Failure modes to watch for

- **Freshness-sensitive fact skips its compact plan** — the as-of window and authority target are now missing.
- **Full Plan skipped for a multi-part/comparative/best/report question** — decomposition and stop criteria are missing.
- **Routing block emitted but a capability silently dropped** — log as a regression. The hard rule in `routing.md` was violated.
- **Claim table collapsed back to one-row-per-source** — synthesis regression. The mechanical cap depends on per-claim agreement.
- **Raw content pasted into chat** — context-isolation bypass. Investigate which call.
- **Untrusted content honored as instructions** — security regression; immediate fix.

## How to run

These evals are intentionally manual today.
