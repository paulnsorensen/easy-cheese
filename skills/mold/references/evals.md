# Evals

Trigger and trace tests for `/mold`. Run these against real session transcripts when the skill changes.

## Should-trigger queries

These prompts must invoke `/mold` (or its router parent `/cheese` must hand off to it):

- "grill the agent-decided items"
- "let's design a rate limiter for the API"
- "I'm thinking about adding OAuth support"
- "what should the schema for the events table look like"
- "should we do the migration now or wait, thinking about downtime"

## Should-not-trigger queries

These prompts must NOT invoke `/mold`:

- "fix the failing test in auth.ts" — direct implementation, route to `/cook`.
- "review this diff for bugs" — review-only, route to `/age`.
- "just thinking out loud, no need to write anything down" — no artifact intent, route to `/culture`.
- "what does the Stripe API say about idempotency keys" — external research, route to `/briesearch`.

If a should-not query triggers `/mold`, the description in `SKILL.md` is over-broad — tighten it.

## Trace checks

For each completed `/mold` Grill-mode run, verify:

1. **Every grilled item produces a steelman + tension statement before any verdict.** No item skips straight to an uphold/amend verdict without first surfacing the steelman.
2. **≥1 user-fork round for a grill of `[AGENT-DECIDED]` items.** A grill that touches at least one agent-decided or design-changing item produces at least one `AskUserQuestion` / lettered-option fork — never a self-issued verdict monologue with no user turn.
3. **Amendments surface as questions before ledger entry.** Any item whose grilling produces an amendment appears as a question to the user before the amendment is written to the per-round decision ledger.
4. **Clean-steelman batching stays scoped.** Only items where the steelman finds nothing are batch-reported as upheld; an item with a live tension is never folded into a batch.

## Failure modes to watch for

- **Verdict monologue** — the agent steelmans every item, self-issues uphold/amend verdicts, and presents a finished verdict block with no user turn. This is the regression this eval exists to catch (see issue #279, and the Grill section in `skills/mold/references/modes.md`).
- **Amendment silently folded into the ledger** — an amendment appears in `Decided` without a prior question to the user. Log as a regression.
- **Over-batching** — an item with a real tension gets swept into the "batch-reported as upheld" exception meant only for clean steelmans.

## How to run

These evals are intentionally manual today.
