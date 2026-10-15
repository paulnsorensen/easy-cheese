---
name: wheel
description: >-
  Runs a repeated task as a resumable loop whose state lives in a wheypoint
  record. Use when the user invokes /wheel, or says "set up a wheel", "loop
  this until it is done", "keep iterating until", "spin the wheel", or "resume
  the wheel <slug>". A call with a new description authors a loop; a call with
  its slug runs it. Do NOT use for a one-time handoff (/wheypoint), a
  fixed-interval timer (/loop), or one implementation task (/cook).
disable-model-invocation: true
argument-hint: "<slug> | <loop description>"
license: MIT
---

# /wheel

`/wheel` turns a repeated task into a loop that survives context loss.
A wheypoint record holds the loop spec and its progress.
The first call authors the loop with the user.
A later call with the slug runs iterations until a stop condition fires.

## Inputs

Parse the text after the skill name.

- A slug, work id, or note path selects **Run** when it resolves to a wheel record whose `work_id` equals the slug exactly.
- Other text is the loop description for **Author**.
- With no text, run `/wheypoint list --grep "wheel:"` and keep only the records whose `record.title` starts with `wheel:`.
  The grep also matches notes and entries; discard those hits.
  Ask the user to pick one or to describe a new loop.

Resolve the argument with `/wheypoint resolve --ref <arg>` before you choose a mode.
`resolve` can match a prefix or substring in later layers, so require an exact slug match on the resolved record.
Treat a non-exact match as no record for Author versus Run and for the collision check.
A record is a wheel record only when its `record.title` starts with `wheel:`; the title is fixed at genesis.
For a resolved record without that prefix, report that it is not a wheel and point to `/cheese --continue <slug>`.
Two or more matches are an ambiguity.
List each match and ask the user to pick one.
Never pick a record by recency.

## Wheypoint access

Use the wheypoint runtime only through `/wheypoint` commands: `resolve`, `list`, `show`, `validate`, and `checkpoint`.
Delegate each checkpoint to `/wheypoint` as one structured checkpoint task.
`/wheypoint` runs `validate` before `checkpoint`, refuses secrets, and writes the projection.
Never edit a generated note.

## Questions

Ask each user question through [`../cheese/references/ask-user-question.md`](../cheese/references/ask-user-question.md).
The spec approval and a gate answer are mechanical questions.
For a design fork, such as a new done check after a stall, state the trade-offs in prose first.

## Loop spec

The record `notes` hold the loop spec in this form.

```markdown
## Wheel
- Goal: <one sentence>
- Step: <what one iteration does; it may name a skill, such as /cook or /affinage>
- Done check: `<command>`; reports <a count>; done when <the count reaches the done value>
- Budget: <N> iterations per run, <M> iterations in total
- Stall: <K> iterations without progress gate the loop
- Scope: <paths, branch, and the changes the step may make>

## Progress
- Iterations: <total>; last run: <date>; last check: <result>; stall count: <n>
- <iteration number>: <one-line outcome>
```

A done check is a command or observation that an agent verifies without judgment.
"Looks good" and "tests mostly pass" are not done checks.
A done check reports a graded result: a count, such as failing tests or open findings, that reaches a done value.
Progress means the graded count moves toward the done value since the previous check; no other signal counts.
An exit code alone is not graded; ask the user for a graded check or add a count command.
Keep a `Stall count` line in `## Progress`: reset it to 0 on progress and add 1 otherwise.
Keep the last five iteration lines, and keep `notes` under 4000 characters.
The stall counter, not the five history lines, decides a stall.

Record these entries in the same checkpoint:

- A `directive` entry with the verbatim `quote` for each user constraint, including any publish permission.
- A `question` entry with `blocks_continuation: true` and a `rationale` for each blocker.
  The rationale states the options, the evidence, and your prior leaning.
- A `question` entry with `blocks_continuation: false` for each open risk that does not block.

## Author

1. **Draft.** Fill the loop spec from the user's text and the conversation.
   Done when each field has a value or a named gap.
2. **Clarify done.** Propose a concrete done-check command.
   Ask the user about each gap in the done check, budget, stall limit, or scope.
   Done when the user confirms the done check.
3. **Baseline.** Run the done check once.
   A pass means the work is already done; report this and stop.
   A check that cannot run is a blocker.
   Done when `## Progress` holds the baseline result.
4. **Scan for blockers.** Check each item in the list below.
   Done when each item is clear or is a recorded blocker.
5. **Approve.** Show the spec, the slug, the blockers, and the open questions in one message.
   Ask for one approval.
   Done when the user approves or edits the draft.
6. **Checkpoint.** Send one task to `/wheypoint` with the slug as `work_id`.
   Set the title to `wheel: <goal>` and `next: hold`; the title is fixed at genesis.
   Set the orientation to the goal.
   Put the spec in `notes` and the scope paths in `working_context`.
   A first checkpoint needs no base.
   Done when `/wheypoint` reports a revision.
7. **Stop.** Report the slug and the start command `/wheel <slug>`.
   Run no iteration in the authoring call.

The blocker scan checks these items.
Items marked (authoring only) do not apply in **Run**:

- The done-check command runs in this checkout and reports a graded result.
- Each skill, CLI, MCP server, and credential that the step needs is present; never print a secret.
- The working tree is clean, or the user accepts the dirty paths. (In Run, dirty paths inside Scope are accepted; others are a blocker.)
- Each branch, pull request, or issue that the step names exists.
- The step needs no user decision in each iteration.
- The step can change the done-check result, so the loop can converge.
- A step that commits, pushes, or publishes, such as `/affinage` or `/plate`, has a `directive` entry with the user's verbatim publish quote.
  Without that quote, the step is a blocker.
- The slug matches `[a-z0-9][a-z0-9._-]{0,63}`, and `resolve` finds no record whose `work_id` equals it exactly. (authoring only)

## Run

1. **Resolve.** Stop at an error that `resolve` reports.
   An integrity finding is any non-advisory finding.
   The advisory codes `stale-commit` and `grounded-path-missing` are show-and-continue.
   A `gated` outcome goes to step 2 only when its detail starts with `active gating entries:`.
   Stop on any other gate detail: validation failures, a missing pinned commit, a missing workspace binding, or a revision mismatch.
   Note the `revision_id` that `resolve` reports.
   Each write in this run passes the `revision_id` from the last read or write as the base through `/wheypoint`.
2. **Read the state.** For `next: done`, report the final progress and stop.
   For `status: gated:`, show each gating entry with its rationale and ask the user.
   Map each answer before you `resolve` the question:
   - stop: checkpoint `next: hold` and exit.
   - change the done check or the spec: update `notes`.
   - publish permission: add a `directive` with the verbatim `quote`.
   Then checkpoint the `resolve` transition with its rationale.
   Continue only when no gate remains.
3. **Rescan.** Run the blocker scan again, without the authoring-only items.
   Checkpoints in **Run** omit `orientation`; the runtime carries it forward.
   For a new blocker, checkpoint it as a gating `question` with a rationale and stop.
4. **Check once.** Run the done check and keep its result as the current result.
   A pass goes to step 6 as `done`.
5. **Iterate.** In each iteration, run these steps in order:
   1. Run the step once, inside the scope and the directives.
   2. Run the done check once; its result is the new current result.
      Compare it with the previous current result; do not run the check a second time.
      The next iteration reuses this result as its previous result.
   3. Update `## Progress` and checkpoint through `/wheypoint` with `next: hold`.
      Pass the `revision_id` from the last read or write as the base, and omit `orientation`.
6. **Stop** when the first condition below fires, and checkpoint the result:
   - `done`: the done check passes; set `next: done`.
   - `budget`: the run budget or the total budget is spent; keep `next: hold`.
   - `stall`: the `Stall count` reaches `K`.
     Add a gating `question` with `blocks_continuation: true` and a rationale: change the step, change the done check, or stop.
   - `blocked`: a new blocker appears, or the step needs a user decision.
     A skill that the step calls can stop at its own gate.
     Add a gating `question` with `blocks_continuation: true` and a rationale that states the options and your leaning.
   - `context`: the context window runs low; the next `/wheel <slug>` resumes.
7. **Report** with the output block below.

## Output

```markdown
wheel: <goal>
Slug: <slug>; iterations: <this run> this run, <total> in total; last check: <result>
Stopped: done | budget | stall | blocked | context
Next: /wheel <slug> | answer the gate: <entry> | none
Wheypoint: [.cheese/notes/<slug>.md](<absolute-note-path>)
```

The authoring call reports `Stopped: authored` and `Next: /wheel <slug>`.

## What this skill never does

- It never runs an iteration in the authoring call; the user starts the loop.
- It never sets `next: done` without a passing done check.
- It never acts past a gate, an integrity finding, or a spent budget.
- It never commits, pushes, or publishes unless a directive quotes the user's permission; the blocker scan checks this for each step.
- It never writes wheypoint state except through `/wheypoint`.
