# Easy-cheese manifesto

Working copy — 2026-10-18.
These tenets preserve the owner's stated direction, with light edits for clarity.
They are not an approved rewrite specification.[^brief]

Easy-cheese should help us turn uncertain ideas into correct, understandable software.
We want an opinionated implementation engine without forcing every problem through the same process.
The workflow should fit the work, not the other way around.

## 1. Research and grounding based on current data

The model cannot be authoritative about the current state of the world.
We should ground our work in current evidence, whether that comes from code, a wiki, or research.
We should seek the latest relevant information and make clear what we know, what we assume, and what remains uncertain.

## 2. Culture, Mold, Pasteurize, and Prototype

We seek information and shape it.
This is not a one-size-fits-all situation.

We should identify as many important unknowns as possible and turn what we learn into clear specifications.
That may not happen in one shot.
It may not be prototype-first.
It may combine conversation, research, diagnosis, experiments, prototypes, and implementation.

There are many “diffusive” ways to get there.
Easy-cheese needs to support them with ease.

## 3. Cook, Age, and Cure

The implementation engine can and should be opinionated.
It should reflect our experience and philosophies about making correct, cost-effective software.

Models can miss the network of ideas, constraints, and responsibilities that eventually becomes code.
Easy-cheese should make those connections explicit without creating friction for the user.

Once something is cooked, it should be up to spec, clean, properly abstracted, and easy to change.
Passing tests is necessary evidence, not the whole goal.

## 4. A network of Wheypoints and LLM wikis

We will always need active context management.
Easy-cheese should connect ideas from different sessions, rather than leave them in isolated handoffs.

We can lean on Hallouminate for indexing.
We should also have clear tooling and decisions about what belongs in durable cheese storage and what belongs in the repository.

Decisions, evidence, open questions, specifications, and results should remain connected.
A future session should recover why we did something, not just what happened last.

## 5. Reviewability and comprehension debt

We must actively manage comprehension debt.
I want to keep Hard-cheese and make it more useful.

By code review, the user should know the shape of the change, what to expect, and why we built it that way.
That may include carefully stacked pull requests, active comments, and Mermaid diagrams.

Reading code without context takes too much time.
Easy-cheese should make understanding and integrating a change easier, not merely generate more code.

## 6. Predictable behavior

Users should be able to `/cheese` everything and let us route the work.
The process should scale to their experience without making them learn our internal machinery.

We should accept natural, incomplete input and produce clear, reliable outputs.
Strongly typed boundaries can help, but they serve the workflow rather than define every thought.

Cheese may be heavier than other flows.
That weight must earn its place through reliability.

## 7. Useful parallelism

Ultracook showed the value of independent implementers working at the same time.
We should preserve that capability without requiring it for every task.

Milknado may become an execution engine, but it should not be a prerequisite.
Parallel work should also support research, design, and review.

We can explore broadly, converge, build some parts, review others, and refine.
The whole change must still fit together.

## 8. Pluggability and portable installation

Easy-cheese installs through `npx skills`.
Its language and tools must work with what the user actually has.

We can prefer other cheese tools without requiring them.
Code intelligence, research, LLM wikis, model providers, and execution tools should remain replaceable.
Missing integrations should produce an honest fallback, not hidden loss of assurance.

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

## Working boundary

These are commitments about the experience and quality we want.
They do not approve a particular storage engine, schema count, agent topology, or rewrite plan.
The [minimal-core discussion](./ideas/minimal-easy-cheese.md) keeps proposals and unresolved choices separate.

[^brief]: Owner's request, T3 thread `b8d02190-bff6-4f67-a1b1-25faf8f2ebc7`, 2026-10-18; checkpoint work ID `easy-cheese-rewrite-manifesto`.
