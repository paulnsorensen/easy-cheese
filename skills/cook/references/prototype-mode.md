# /cook — Prototype mode

Prototype mode is a steered build loop for an idea that has no spec.
The user says "here is an idea, go prototype it."
Cook builds a working first cut, shows it, and refines it with the user round by round.
The code stays.
When the shape settles, Cook stabilizes it into tested, reviewable work.

## When to enter

Enter on `--prototype`, or when the ask has a prototype signal:

- "prototype this", "go prototype it", "spike this out", "hack up a first version".
- "build a rough version and we'll iterate", "let's try it and see".

Prototype mode is for exploration.
It is not a replacement for the standalone fast-path when the task is already clear.
It is not the Mold Prototype Cycle.
The Mold cycle answers one design question in a throwaway worktree and discards the code.
Prototype mode keeps the code and grows it.

## Setup

1. Derive a kebab-case slug from the ask.
2. If the working tree is dirty, stop and ask the user to commit or stash first.
3. Record the base commit and the original branch.
   Stabilize uses the base commit to prove new tests fail without the prototype.
4. If the current branch is the default branch, create a branch before the first edit.
   Record that Setup created it.
   Otherwise, record the current branch as the original branch and that Setup made no new branch.
5. Run the leverage-trigger check in [`../../cheese/references/routing-policy.md`](../../cheese/references/routing-policy.md) § Leverage triggers.
   Announce each fired id.
   A fired trigger does not stop the loop, but it changes the stabilize route.
6. Start the prototype log in `.cheese/cook/<slug>.md` under `## Prototype log`.
   Do not create a second file.

## The round

Each round has three steps.
Keep each round small enough for the user to check in one read.

1. **Plan** — Show three to five bullets.
   Name the next step, the files it touches, and what the user sees at the end of the round.
   Do not write a spec file.
   Do not wait for approval unless the step is destructive or a new trigger fires.
2. **Spike** — Build the step for real in the working tree.
   Prefer the simplest working path and existing project patterns.
   Run the cheapest check that shows the step works.
   Use an existing test, the app, a command, or a script.
   The Iron Law RED step does not apply to spike code; stabilize closes that gap.
3. **Check** — Report what changed, the evidence that it works, and each open question.
   Append one entry to the prototype log: the plan, the files, and the evidence.
   Then offer this menu and wait:
   - **Refine** — the user gives feedback; start the next round.
   - **Stabilize** — the shape is right; go to § Stabilize.
   - **Discard** — delete the prototype; see § Discard.
   - **Checkpoint & stop** — `/wheypoint`.
   Append the user's reply to that entry before the next round, Stabilize, or Discard.

Run the leverage-trigger check again in each Plan step.
Announce a newly fired id before the Spike step.

## Loop rules

- Keep every change on the prototype branch; never commit to the default branch.
- Do not run `/plate`, push, or open a pull request during the loop.
- Do not delete user work or run a destructive operation without an explicit yes.
- Do not add scope the user did not ask for; list ideas as open questions instead.
- Report a failed check as failed; never present an unrun check as passing.
- `--auto` does not skip the Check step; it applies only after stabilize.

## Stabilize

Stabilize converts the prototype into normal Cook work.

1. Draft the acceptance criteria from the behavior the user accepted in the prototype log.
   Each criterion traces to a log entry.
2. Route by the leverage triggers:
   - **No fired trigger** — invoke `/mold` in agent-invoked mini-spec mode ([`../../mold/references/mini-spec-mode.md`](../../mold/references/mini-spec-mode.md)) as a visible handoff.
     Record the prototype log path in `## Provenance`.
     If the user declines Cook consent, keep the prototype branch and the saved draft.
     Then stop Stabilize and return to the prototype menu.
   - **A fired trigger** — stop and route to `/mold` at Light tier.
     Pass the prototype log and the branch as prior evidence.
     Mold confirms each consequential fork before Cook continues.
3. Run the normal Cook Flow from **Contract** against the spec, with the prototype tree as the start state.
4. Write a test for each criterion.
   Prove each test fails without the prototype behavior before it counts as RED.
   Run it against the base commit, or disable the behavior and restore it after the RED run.
   A test that never fails does not satisfy the Iron Law.
5. Remove spike debris that no criterion needs, such as debug output and unused paths.
6. Continue with **Validate**, **Taste-test**, and **Hand off** as the Flow defines.
   The handoff slug `artifact:` names the minted spec.
   Pass `--body-file` with a body that keeps the full `## Prototype log` section.

## Discard

Show the files and branch that the discard removes.
Ask for an explicit yes.
After the yes, restore the working tree to the base commit.
Check out the original branch.
Delete the prototype branch only when Setup created it.
Keep the prototype log; it records what the loop learned.
Write the handoff slug with `next: done` and a one-line orientation that names the discard.
Pass `--body-file` with a body that keeps the full `## Prototype log` section.
