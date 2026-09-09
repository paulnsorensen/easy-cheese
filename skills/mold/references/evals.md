# Evals

Trigger and trace tests for `/mold`. Run these against real session transcripts when the skill changes.

## Should-trigger queries

These prompts must invoke `/mold` (or its router parent `/cheese` must hand off to it):

- "grill the agent-decided items"
- "let's design a rate limiter for the API"
- "I'm thinking about adding OAuth support"
- "what should the schema for the events table look like"
- "should we do the migration now or wait, thinking about downtime"
- "/mold rename the `parse_flags` helper to `parse_args` in cli.py" — must trigger, and must land in the **Quick** tier: one confirm, a mini-spec, no fork questions (`tiers.md`).

## Should-not-trigger queries

These prompts must NOT invoke `/mold`:

- "fix the failing test in auth.ts" — direct implementation, route to `/cook`.
- "review this diff for bugs" — review-only, route to `/age`.
- "just thinking out loud, no need to write anything down" — no artifact intent, route to `/culture`.
- "what does the Stripe API say about idempotency keys" — external research, route to `/briesearch`.

If a should-not query triggers `/mold`, the description in `SKILL.md` is over-broad — tighten it.

## Trace checks

For every completed `/mold` run, verify first that the tier was announced in one line with its reason before the first fork question, and that any tier change was an announced upgrade, never a silent downgrade (`tiers.md`).

For each completed `/mold` Grill-mode run, verify:

1. **Every grilled item produces a steelman + tension statement before any verdict.** Do not proceed directly to an uphold or amend verdict. Surface the steelman first.
2. **One user-fork round or more for each consequential grilled item.** Consequential is the leverage line in [`../../age/references/voice.md`](../../age/references/voice.md). Invoke the question primitive at least once for each consequential item. Use `AskUserQuestion` on Claude Code and Conductor. On another harness, use the equivalent in [`ask-user-question.md`](../../cheese/references/ask-user-question.md). Require a real user turn. Never render and answer an `A/B/C/D` block yourself. Never issue a verdict monologue on a consequential item without a user turn. Items below the leverage line are batch-reported as upheld with a one-line steelman and never become a user turn; a user turn spent on one is a regression.
3. **Amendments surface as questions before ledger entry.** Ask the user about each amendment that a grill produces. Ask before you write the amendment to the per-round decision ledger.
4. **Clean-steelman batching stays scoped.** Batch-report a consequential item as upheld only when its steelman finds nothing. Never include a consequential item with a live tension in a batch. Below-the-line items always batch, tension or not; the ledger carries their vetoable alternative.
5. **Every user fork names what it moves.** Each `Asking` entry cites the acceptance criterion, public seam, or non-goal it changes. A fork with no such target is `[AGENT-DECIDED]` or a follow-up candidate, never a question.
6. **The `Goal:` line survives every round.** The ledger repeats the pinned goal verbatim from the bounds pass to the handshake. A reworded goal traces to an explicit user fork.

## Failure modes to watch for

- **Verdict monologue** — the agent steelmans every item, self-issues uphold/amend verdicts, and presents a finished verdict block with no user turn. This is the regression this eval exists to catch (see issue #279, and the Grill section in `skills/mold/references/modes.md`).
- **Amendment silently folded into the ledger** — an amendment appears in `Decided` without a prior question to the user. Log as a regression.
- **Over-batching** — a consequential item with a real tension gets swept into the "batch-reported as upheld" exception meant only for clean steelmans.
- **Under-batching** — a below-the-line item (naming, internal scope, a trade-off that fires no trigger) gets its own user turn instead of a ledger line.
- **Altitude drift** — three or more consecutive forks move no acceptance criterion, seam, or non-goal, and the decision map never renders. The rabbit hole this eval exists to catch: every noun traces to the user, so the noun-level scope gates stay green while the dialogue burrows.
- **Goal fade** — the `Goal:` line drops out of the ledger render or silently rewords. The taste test catches the terminal form as `goal-drift`; the per-round render is the early form.

## How to run

These evals are intentionally manual today.
