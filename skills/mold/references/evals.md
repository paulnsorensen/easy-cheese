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
7. **Every `G-n` clause reaches the handshake with a disposition.** The bounds pass prints the clauses. The narrowing delta names each one as covered, follow-up, non-goal, or `[TBD]`. A spec that covers fewer than half the clauses triggers a re-pin-or-widen fork, never a silent proceed.

## Failure modes to watch for

- **Verdict monologue** — the agent steelmans every item, self-issues uphold/amend verdicts, and presents a finished verdict block with no user turn. This is the regression this eval exists to catch (see issue #279, and the Grill section in `skills/mold/references/modes.md`).
- **Amendment silently folded into the ledger** — an amendment appears in `Decided` without a prior question to the user. Log as a regression.
- **Over-batching** — a consequential item with a real tension gets swept into the "batch-reported as upheld" exception meant only for clean steelmans.
- **Under-batching** — a below-the-line item (naming, internal scope, a trade-off that fires no trigger) gets its own user turn instead of a ledger line.
- **Altitude drift** — three or more consecutive forks move no acceptance criterion, seam, or non-goal, and the decision map never renders. The rabbit hole this eval exists to catch: every noun traces to the user, so the noun-level scope gates stay green while the dialogue burrows.
- **Terse fork** — a consequential question shows bare option labels with no fork card, no `Decides:` line, or no branch symbols or graph. Or it offers no `Explain more` choice, or it answers an unclear reply with a guess or a new fork. See `fork-questions.md`.
- **Goal fade** — the `Goal:` line drops out of the ledger render or silently rewords. The taste test catches the terminal form as `goal-drift`; the per-round render is the early form.
- **Quarter build** — the goal sentence survives and every noun traces, but Acceptance delivers a fraction of the clauses and the agent presents the slice as the whole. The pre-check catches the terminal form as `goal-coverage:G-n` or `goal-coverage-cap`; a missing narrowing delta at the handshake is the early form.
- **Spec altitude drift** — the draft spec fills Interface sketches with code, schema, or config bodies, or it reads as a slogan with no rejected option. The altitude evals below catch both forms.
- **Wrong diagram level** — Approach opens with no diagram, with a view that the `diagrams.md` checklist does not select, or with a C4 Code-level drawing. The altitude evals below check the opening diagram.

## Mold-to-Cook live trace

Run this scenario with a fresh task agent in an isolated repository. Supply the changed Mold bundle.

1. Give the agent a strict, valid spec that needs two curds.
2. Supply a typed planner result and explicit user Cook selection as separate host events.
3. Require `scripts/mold.pyz finalize`; reject any `publish` command or fabricated execution refs.
4. Pass the returned `request_id`, `spec_ref`, `planner_result_ref`, `plan_ref`, and `coverage` to bound validation and execution.
5. Capture actual tool calls, any bounded runner response and setup evidence, and the final artifact.

The trace passes only when the checker accepts it, Cook validates the exact refs, and execution produces the selected curds. An unresolved hold must prevent ready finalization.

## Altitude evals

[`../evals/evals.json`](../evals/evals.json) holds 16 altitude cases in the Agent Skills `evals.json` shape.
The `/skillz autoimprove` runner seeds its task cases from the same file.
The cases check that a Mold spec decides seams and trade-offs at design altitude.
They also check that its diagrams follow [`diagrams.md`](../../cheese/references/diagrams.md).
Each of the eight topics has two cases:

- **Draft case** (`al-<topic>`): Mold reads `evals/files/al-<topic>/problem.md` and writes a draft spec. The fixture records the user's fork decisions from an earlier round and leaves one consequential fork open. Mold writes the recorded decisions as the user's decisions. It keeps the open fork open, with a `handshake.md` marker and an `execution_holds` entry, because consequential forks are the user's to pick. The run stops at the readiness check.
- **Pick case** (`al-<topic>-pick`): Mold labels three drafts in `evals/files/al-<topic>-pick/drafts.md` as `too-low`, `right`, or `too-high`.

In each pick fixture, the `too-low` draft holds bodies, helper signatures, or code-level detail. The `too-high` draft is a slogan. The `right` draft decides seams and opens with a diagram.
All three drafts show the same surface sections: a Mermaid diagram, a title, `Problem`, `Decision`, `Crux`, a full Placement block, `Rejected`, `Out of scope`, and `Verification`.
The length, line, and sentence order of the drafts changes from topic to topic.
Thus no section, field, fence, or length gives away the label, and the grader must read what each draft says.
The topics paraphrase public design documents: a Kubernetes enhancement, a Rust RFC, a Python PEP, and two Oxide RFDs.
Three topics are original system-design prompts.
Each fixture cites its source and copies no sentence.

| ID | Check | Mold rule |
| --- | --- | --- |
| `R-ALT-ACTOR` | Problem states what is broken or missing and who feels it, and keeps the pinned goal. Word order does not matter. | `curdle.md` § Spec template |
| `R-ALT-SEAMS` | Interface sketches hold no code body, helper signature, or internal pseudocode. The Placement block with public signatures is not a body. | `modes.md` § Sketch |
| `R-ALT-CRUX` | Depth goes to the consequential decisions; each routine part gets one line. No fixed fork count applies. | Leverage line in `../../age/references/voice.md` |
| `R-ALT-DECIDE` | Each material choice states the decision and a reason for each rejected option. | `modes.md` § Shape |
| `R-ALT-HOLD` | The spec writes each recorded decision as the user's decision, and keeps the open fork open, marked `[TBD]`, `[?]`, or `[BLOCKED]`, with an `execution_holds` entry. | `SKILL.md` § Flow steps 3 and 6; `handshake.md` § Agent key |
| `R-ALT-SCOPE` | Each non-goal traces to the fixture, or carries `[AGENT-INTRODUCED]` with a scope audit row; an unresolved row keeps the draft from ready. | `handshake.md` § Non-goals audit |
| `R-ALT-DIAGRAM` | Approach opens with the view that the checklist selects, with each static C4 view drawn as a `flowchart`, and at most two more diagrams. | `../../cheese/references/formatting.md` § Spec |
| `R-ALT-PICK` | Each pick label matches `expected_output`. | All rows above |
| `R-ALT-PICK-WHY` | Each pick label quotes a span: a strength for `right`, the defect for the other labels. | All rows above |
| `Q-ALTITUDE` | A 1–5 quality scale over the rows above. | All rows above |

Grade a pick case against its answer key in `expected_output`.
In a draft case, every code fence in the Interface sketches section of `answer/spec.md` must be `mermaid` or the `text` Placement block.
The rest of the spec may hold the fences that the spec template uses, such as the frontmatter and the EARS block.
A model grader scores the remaining assertions.
`tests/python/test_mold_altitude_evals.py` keeps the cases, fixtures, and answer keys consistent, and it pins each pick key.
It also fails when one surface feature, or one length, line, sentence, or word-count rank, predicts more than half of the pick keys.

## Diagram evals

The same file holds 17 diagram cases.
They check that Mold picks diagrams with [`diagrams.md`](../../cheese/references/diagrams.md).
They come in two kinds:

- **View case** (`dg-view-<view>`): Mold reads `evals/files/dg-view-<view>/change.md` and writes only the Approach diagrams. Fourteen cases cover each checklist view, two overlap rules, and an author who asks for every view. Each fixture states which elements already exist, so that only the expected checklist item applies.
- **Fork-card case** (`dg-fork-<kind>`): Mold reads a Shape ledger in `evals/files/dg-fork-<kind>/state.md` and writes the fork card of each fork. The host does not render Mermaid. A fork that changes flow, ownership, or order gets a `text` graph for each branch. A fork about a date, a metric, or a policy gets a symbol table. Each ledger has three or more forks, so its tier is Full.

Each change and state is an original prompt about a generic shop, ledger, or API.

| ID | Check | Mold rule |
| --- | --- | --- |
| `R-DIAG-VIEW` | Approach opens with the one view that the checklist and smallest-set rules select, and draws no view that an overlap rule replaces. | `diagrams.md` § When to draw, § Draw the smallest set |
| `R-DIAG-SMALLEST` | An author who asks for many diagrams gets the opening diagram and at most two more, including the riskiest. | `../../cheese/references/formatting.md` § Spec |
| `R-DIAG-NOTATION` | Static C4 views are a `flowchart`; each diagram has 15 nodes or fewer, no `end` node id, and no style directive. | `diagrams.md` § Notation rules, § Mermaid rules |
| `Q-DIAG-FIT` | A 1–5 quality scale for the reader question, the scope, and the labels. | `diagrams.md` § Pick one view |
| `R-FORK-GRAPH` | A fork that changes flow, ownership, or order draws each branch as a `text` graph of eight lines or fewer. | `fork-questions.md` § Fork card |
| `R-FORK-C4` | An architecture fork names its C4 level and elements. | `fork-questions.md` § Fork card |
| `R-FORK-TABLE` | A fork whose branches differ only in properties uses a symbol table and no graph. | `fork-questions.md` § Fork card |
| `R-FORK-NO-MERMAID` | A terminal host gets no mermaid fence in a fork card. | `fork-questions.md` § Fork card |
| `R-FORK-FIELDS` | Each card holds the title, `Decides:`, `Moves:`, `Today:`, the branches, and `Legend:`. | `fork-questions.md` § Fork card |
| `Q-FORK-FIT` | A 1–5 quality scale for the fork-card graphs. Only architecture graphs name a C4 level. | `fork-questions.md` § Fork card |

A model grader scores every diagram assertion against `expected_output`.

## Families

Each case has a `family`. A family never crosses a train, validation, or holdout split, and the splitter needs at least three families.
Each altitude draft case shares its family with its pick case, so a near-copy never reaches the holdout split.

| Family | Cases |
| --- | --- |
| `alt-runtime` | `al-kep-credential-plugin`, `al-rate-limiter-outage`, and their pick cases |
| `alt-rack` | `al-oxide-control-plane-db`, `al-oxide-bootstrap-network`, and their pick cases |
| `alt-language` | `al-rfc-dyn-trait`, `al-pep-dataclasses`, and their pick cases |
| `alt-product` | `al-ticket-hold`, `al-crux-depth`, and their pick cases |
| `diag-structure` | the container, component, context, landscape, deployment, and overlap-container views, and `dg-fork-structure` |
| `diag-behavior` | the sequence, async-sequence, agent-handoff, flow, and overlap-async views, and `dg-fork-behavior` |
| `diag-data` | the database, state, and pressure views, and `dg-fork-data` |

## How to run

These evals are manual today.
The owner deferred the grader and the first live journey run (manifesto ruling F).
A `/skillz autoimprove` run stages only `skills/mold`.
The prompts and the Mold rules read `../cheese` and `../age`, so a run needs a contract that lists those directories in `surface.companions`.
That contract, its graders, and its budget need the owner's approval before a live run.
