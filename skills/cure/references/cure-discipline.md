# /cure — Fix-Application Discipline

## Iron Law

**No finding is Applied until a passing gate proves the fix.**

An edit alone does not make a finding Applied.
Run the narrowest proving test after each fix.
Then run each relevant project gate.
Move a finding to `### Applied` only after these checks pass.
Keep an unvalidated fix in staged state.

---

## Red Flags

Stop when you notice one of these thoughts:

- "The fix is obvious, so I can skip its test."
- "I can test all fixes together at the end."
- "The finding gives enough context, so I can skip a fresh read."
- "The Age report is wrong, but I can apply its fix anyway."
- "One edit fixes all findings, so I can skip separate checks."
- "I can mark this finding Applied while a gate remains red."

Each thought is a rationalization.
Name it and stop.

---

## Rationalization table

| Rationalization | Why it fails | Required action |
| --- | --- | --- |
| "The fix is obvious, so tests are unnecessary." | An unchecked fix can introduce a subtle regression. | Run the narrowest proving test before you mark Applied. |
| "I can validate all fixes at the end." | A later failure does not identify which fix caused it. | Validate each fix in order. |
| "The finding has a false premise, so I can skip it." | A silent skip hides a disagreement with the report. | Put the finding in Deferred with the rebuttal. |
| "The location is clear, so I can skip a fresh read." | A stale location can send an edit to the wrong anchor. | Read the cited location again before every edit. Follow the [shared routing contract](../../cheese/references/code-intelligence-routing.md). |
| "One root cause means one check is enough." | One edit can affect findings in different ways. | Apply once and validate. Then check every related finding again. |
| "The gate is flaky, so I can mark Applied." | A red gate cannot prove the fix. | Record the failure in Checks. Keep the finding out of Applied. |
| "A low severity lets me skip validation." | Severity measures impact, not validation need. | Validate every applied fix. |

---

## Bounded responsibility on dispatch

A repair agent owns only the findings in its brief.
Do not add nearby cleanup, repeat the review, or expand the scope.
This limit makes another dispatch safe and specific.

Before a near-limit stop, return one structured handoff with these parts:

- **Completed.** List each Applied finding and its verification result.
  Keep an unvalidated fix in staged state.
- **Changed-file ownership.** List every file that the agent changed.
- **Remaining.** List each unfinished finding and its exact next action.
- **Blockers.** List each environment or tool failure.

The orchestrator must use this handoff for the next dispatch.
Give the next agent the completed set and the next action.
Do not restart the full finding set.

A limit stop keeps the `BLOCKED` disposition.
The first `unresolved_work` entry starts with `writer stopped at its budget:`.
Use `budget checkpoint invalid:` when checkpoint validation fails.
These prefixes distinguish a limit stop from an executor failure.

`easy_cheese_schemas.workflow.WriterBudgetExceeded` defines this seam.
It carries a `WriterCheckpoint` with the four handoff parts.
The `reason` text carries the blocker and the limit cause.
The host finalizes the checkpoint as a partial curd result.
Completed criteria keep their disposition and evidence.
Unreached criteria receive the limit reason.
List completed criteria in criterion order.
List only finished criteria as completed.
A failed checkpoint can still preserve readable deliverables.
Reject a checkpoint that claims every criterion.
The limit path skips review, so full coverage has no review evidence.
