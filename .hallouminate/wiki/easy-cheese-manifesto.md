# Easy-cheese manifesto

Working copy — 2026-10-18, updated 2026-10-22 with the owner's rulings.
This page is the one canonical copy of the tenets, and `AGENTS.md` links to it.
These tenets preserve the owner's stated direction, with light edits for clarity.
The [rulings](#rulings) section records what the owner decided.[^brief][^rulings]

Easy-cheese should help us turn uncertain ideas into correct, understandable software.
We want an opinionated implementation engine without forcing every problem through the same process.
The workflow should fit the work, not the other way around.

## 1. Research and grounding based on current data

The model cannot be authoritative about the current state of the world.
We should ground our work in current evidence, whether that comes from code, a wiki, or research.
We should seek the latest relevant information and make clear what we know, what we assume, and what remains uncertain.
A wiki page can be stale too.

## 2. Culture, Mold, Pasteurize, and Prototype

We seek information and shape it.
This is not a one-size-fits-all situation.

We should identify as many important unknowns as possible and turn what we learn into clear specifications.
That may not happen in one shot.
It may not be prototype-first.
It may combine conversation, research, diagnosis, experiments, prototypes, and implementation.

There are many “diffusive” ways to get there.
Easy-cheese needs to support them with ease.

A piece that is ready during shaping starts at once.
When a specification section changes under a piece in flight, the piece finishes and a follow-up piece is queued.
A change in direction cancels the piece and resends it.
Mold's full ceremony applies when a piece goes to a cold executor or changes a public contract.

## 3. Cook, Age, and Cure

The implementation engine can and should be opinionated.
It should reflect our experience and philosophies about making correct, cost-effective software.

Humans own intent, trade-offs, and acceptance.
Easy-cheese makes the network of ideas, constraints, and responsibilities behind the code inspectable at that altitude, without creating friction for the user.

Once something is cooked, it should be up to spec, clean, properly abstracted, and easy to change.
Passing tests is necessary evidence, not the whole goal.
An opinion that matters lives in code or an eval, not only in prose.

## 4. A network of Wheypoints and LLM wikis

We will always need active context management.
Easy-cheese should connect ideas from different sessions, rather than leave them in isolated handoffs.

We can lean on Hallouminate for indexing.
We should also have clear tooling and decisions about what belongs in durable cheese storage and what belongs in the repository.

Decisions, evidence, open questions, specifications, and results should remain connected.
A future session should recover why we did something, not just what happened last.
The Wheypoint record links to Spec, Plan, and Review artifacts as first-class citizens and pins each link by digest; it does not embed them.

## 5. Reviewability and comprehension debt

We must actively manage comprehension debt.
I want to keep Hard-cheese and make it more useful.

By code review, the user should know the shape of the change, what to expect, and why we built it that way.
That may include carefully stacked pull requests, active comments, and Mermaid diagrams.

Reading code without context takes too much time.
Easy-cheese should make understanding and integrating a change easier, not merely generate more code.

Hard-cheese stays the quiz at publication.
A separate review artifact carries the shape, the expectations, and the why through the work.

## 6. Predictable behavior

Users should be able to `/cheese` everything and let us route the work.
The process should scale to their experience without making them learn our internal machinery.

We should accept natural, incomplete input and produce clear, reliable outputs.
Strongly typed boundaries can help, but they serve the workflow rather than define every thought.

Three words keep this exact:

- An **artifact schema** is the shape of a stored thing, such as a Spec, a Plan, or a Review.
- A **receipt** is evidence that code computes, such as a check result or a digest.
- A **gate** is a blocked transition. No gate exists between phases; typed exits stay at consequential boundaries.

Cheese may be heavier than other flows.
That weight must earn its place through reliability.

## 7. Useful parallelism

Ultracook showed the value of independent implementers working at the same time.
We preserve that capability, and each split must earn its place.

Cook's shape follows size heuristics in code.
Small work cooks inline, one sizeable piece goes to a fresh-context worker with its grounding plan in the spec, and several pieces run in parallel with a mix of dispatched and inline work.
Milknado stays the parallel executor; it is an optional plugin that couples to easy-cheese through artifact pointers only.
Parallel work should also support research, design, and review.

We can explore broadly, converge, build some parts, review others, and refine.
The whole change must still fit together.

## 8. Pluggability and portable installation

Easy-cheese installs through `npx skills`.
Its language and tools must work with what the user actually has.

We can prefer other cheese tools without requiring them.
Code intelligence, research, LLM wikis, model providers, and execution tools should remain replaceable.
Missing integrations should produce an honest fallback, not hidden loss of assurance.

The core is harness-neutral.
Shared skill text names roles and model tiers, not models.
A thin overlay per harness and model, generated where possible, holds the rest.
A Codex model never receives instructions tuned for Opus.

## 9. Deterministic mechanics

We should waste as few tokens as possible on logic that a CLI can perform.
Validation, bookkeeping, state transitions, and other mechanical work belong in code when that makes the system simpler and more reliable.

There is a trade-off.
We should not build machinery merely because we can.
The goal is reliable behavior and efficient use of context, tokens, and time.

## 10. Powered by skillz-that-grillz

I extracted my best libraries into `paulnsorensen/skillz-that-grillz`.
Easy-cheese should use that foundation instead of rebuilding it.

We should explain how cheese works through user journeys and evaluations.
Those journeys should let models test and refine cheese as it changes and ages.
Improvement should mean better outcomes for users, not just better scores on our own checks.

## 11. Scale the process to the work

If a user wants a full waterfall specification, we support it.
If they need a bug fix, we do not create nineteen Opus reviewers.

We use the minimum process and agent effort that can meet the quality bar.
Small work should feel small.
Large work should gain structure where that structure helps.

## 12. UI-native when it helps

Much of this work happens above the level of an individual bug fix.
Visual aids and web interfaces should help even novice users understand the problem and participate.

A UI is useful, but it is not required.
The same work must remain possible through conversation and portable artifacts.
For now the canvas gives feedback: it returns pins and answers, and the agent stays the only writer of the specification.

## Rulings

| Topic | Ruling | Record |
| --- | --- | --- |
| A, design-target harness | Generic agents; the harness must not matter; thin generated overlays per harness and model | [codex-omp-portability-002](./adr/codex-omp-portability-002.md) |
| B, fan-out default | No default; size heuristics in code decide cook's shape | [deterministic-fanout-sizing-005](./adr/deterministic-fanout-sizing-005.md) |
| C, record ontology | Separate Spec, Plan, and Review artifact schemas, linked from the record with digest pins | [workflow-contract-milknado-seam-007](./adr/workflow-contract-milknado-seam-007.md) |
| I, reviewability | Hard-cheese stays the quiz; a review artifact carries understanding | [hard-cheese-retained-002](./adr/hard-cheese-retained-002.md) |
| J, milknado | Optional plugin, pointer coupling at the artifact boundary | [workflow-contract-milknado-seam-008](./adr/workflow-contract-milknado-seam-008.md) |
| Stream promotion line | Full ceremony for a cold executor or a public contract | [deterministic-fanout-sizing-005](./adr/deterministic-fanout-sizing-005.md) |
| Stream in-flight edit | Finish and queue; a change in direction cancels and resends | [deterministic-fanout-sizing-005](./adr/deterministic-fanout-sizing-005.md) |
| Stream canvas role | Feedback only, for now | Tenet 12 |
| Gate vocabulary | Artifact schema, receipt, gate; no gate between phases | Tenet 6 |
| Human altitude | A goal about human ownership, not a claim about model limits | Tenet 3 |
| Sequencing | Make the ruled changes first, measure after, and correct course if a change proves wrong | This page |
| G, further record cuts | Closed as done by #776; later cuts wait for the fork C links | Issue #843 |
| E, skill cuts | Later; the six-versus-fifteen workflow map stays open until then | Deferred |
| F, grader and first live journey run | After the tilth benchmark work | Deferred |
| H, one archive or thirteen | Owner's call; thirteen archives today | Deferred |

## Working boundary

These tenets do not approve a particular storage engine, schema count, or wholesale rewrite.
The ruled changes proceed before a baseline measurement exists; that risk is accepted.
The [minimal-core discussion](./ideas/minimal-easy-cheese.md) keeps proposals and unresolved choices separate.
The evidence bundle behind the rulings lives in `docs/research/manifesto-2026-10/`.

[^brief]: Owner's request, T3 thread `b8d02190-bff6-4f67-a1b1-25faf8f2ebc7`, 2026-10-18; checkpoint work ID `easy-cheese-rewrite-manifesto`.
[^rulings]: Forks A, B, C, I, and J: owner rulings of 2026-10-18, recorded in Wheypoint `tenet-sweep-follow-ups@rev-607d0446c9b8` and #832. Other rows: owner rulings of 2026-10-19 to 2026-10-22, recorded in Wheypoint `tenet-reconciliation-rulings@rev-6ab03e394c3f`.

_Source: owner's 2026-10-18 brief and 2026-10-18 to 2026-10-22 rulings · Updated: 2026-10-22._
