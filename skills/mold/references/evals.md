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
2. **≥1 user-fork round for a grill of `[AGENT-DECIDED]` items.** A grill that touches at least one agent-decided or design-changing item invokes the question primitive at least once (`AskUserQuestion` on Claude Code/Conductor, the equivalent per [`ask-user-question.md`](../../cheese/references/ask-user-question.md) on other harnesses) — an actual user turn, never an `A/B/C/D` block the agent renders and answers itself, and never a self-issued verdict monologue with no user turn.
3. **Amendments surface as questions before ledger entry.** Any item whose grilling produces an amendment appears as a question to the user before the amendment is written to the per-round decision ledger.
4. **Clean-steelman batching stays scoped.** Only items where the steelman finds nothing are batch-reported as upheld; an item with a live tension is never folded into a batch.

## Failure modes to watch for

- **Verdict monologue** — the agent steelmans every item, self-issues uphold/amend verdicts, and presents a finished verdict block with no user turn. This is the regression this eval exists to catch (see issue #279, and the Grill section in `skills/mold/references/modes.md`).
- **Amendment silently folded into the ledger** — an amendment appears in `Decided` without a prior question to the user. Log as a regression.
- **Over-batching** — an item with a real tension gets swept into the "batch-reported as upheld" exception meant only for clean steelmans.

## Manual transcript cases

### Overloaded term → Ground → durable writes

- **Setup:** the user uses “account” for both a login identity and a billing customer.
- **Expected dialogue:** Ground pauses for a canonical-term question and records the chosen terms plus the rejected ambiguous synonym.
- **Expected Curdle:** after the handshake, the glossary/domain-model flush writes `.cheese/glossary/<slug>.md`, merges the same terms into the cumulative domain model, reads both back, and names both in the completion record.

### ADR eligibility matrix

Run four decision transcripts and inspect the spec decision log plus durable ADR output:

- **Qualifies: all three** — hard to reverse, surprising without context, and produced by a real trade-off; write one ADR and retain its decision-log index entry.
- **Reject: missing hard to reverse** — surprising and traded off, but cheaply reversible; keep only the spec decision-log entry and write no ADR.
- **Reject: missing surprising without context** — hard to reverse and traded off, but rationale is obvious from code and spec; keep only the spec decision-log entry and write no ADR.
- **Reject: missing real trade-off** — hard to reverse and surprising, but forced by a constraint with no viable alternative; keep only the spec decision-log entry and write no ADR.

### Ambiguous second-context routing

- **Setup:** one domain-model context exists and a resolved term could belong to either it or a new bounded context.
- **Expected dialogue:** Mold names the candidate contexts and asks the user which context owns the term rather than inferring ownership.
- **Expected Curdle:** Mold writes only the selected context, leaves the other context pages unchanged, and records only the confirmed relationship in `domain-model/index.md`.

## How to run

These evals are intentionally manual today.
