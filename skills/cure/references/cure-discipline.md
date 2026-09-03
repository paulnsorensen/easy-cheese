# /cure — Fix-Application Discipline

## Iron Law

**No finding is "fixed" without a gate-passing test run to prove it.**

Applying an edit is not the same as curing a finding. Every applied fix runs
the narrowest test that proves the fix, then any relevant project-wide gates,
before the finding moves to `### Applied`. A fix whose tests were not run is
not applied — it is staged.

---

## Red Flags

Stop if you notice yourself thinking any of these:

- "The fix is obviously correct; running tests is formality."
- "I'll run the full suite at the end rather than after each fix."
- "The finding description is clear enough; I don't need to re-read the
  cited code before applying."
- "The age report is wrong about this finding; I'll apply the fix anyway and
  note it."
- "All findings came from one logical problem; I can fix them in one edit
  without validating each."
- Declaring a finding `### Applied` while any gate is still red.

Each of these is a rationalization. Name it and stop.

---

## Rationalization table

| Rationalization | Why it fails | Required action |
| --- | --- | --- |
| "The fix is obviously correct; tests are formality." | "Obvious" fixes introduce subtle regressions at a higher rate than non-obvious ones, because they skip the mental check that a test encodes. | Run the narrowest test that proves the fix before marking Applied. |
| "I'll validate all fixes together at the end." | A later test failure cannot be attributed to a specific fix without re-running individual ones. Batched validation hides which fix broke what. | Validate each fix individually, in order. |
| "The finding rests on a false premise; I'll skip it." | Silently skipping a finding is not the same as disagreeing with it. If the age claim is wrong, say so in the report. | Put the finding in Deferred with the rebuttal. Do not silently drop it. |
| "I don't need to re-read the code; the finding location is clear." | Fix locations shift during a cure pass. A stale read produces an edit at the wrong anchor. | Re-read the cited location through a fresh bounded read before every edit; follow the [shared routing contract](../../cheese/references/code-intelligence-routing.md). |
| "All findings stem from one root cause; one edit covers all." | This may be true, but it must be verified. Apply the edit, run the gate, then re-check which remaining findings the gate result clears. | Apply once, validate, then re-read each remaining finding to confirm it is resolved. |
| "The gate is flaky; I'll mark the fix Applied and note the flakiness." | A flaky gate is a blocker, not an excuse. Marking Applied on a red gate means the cure report lies. | Record the flakiness in Checks. Do not mark Applied. Surface the blocker. |
| "This finding is low severity; I can skip validation to save time." | Low-severity fixes fail tests at the same rate as high-severity ones. Severity is about impact, not about validation cost. | Validate every applied fix regardless of severity. |

---

## Bounded responsibility on dispatch

A dispatched repair agent owns exactly the findings named in its brief — no
adjacent cleanup, no re-review, no scope it discovered on the way. That bound
is what makes a redispatch cheap: the orchestrator knows precisely which
findings a returning agent was accountable for.

**Near-budget checkpoint.** An agent approaching its context or tool budget
must not die on a bare error. Before it stops it returns, in one structured
handoff:

- **Completed** — each finding it cured, with the verification it ran and the
  result (the Iron Law still applies; an unvalidated fix is staged, not cured).
- **Changed-file ownership** — every file it wrote, so the orchestrator never
  re-derives the diff.
- **Remaining** — the unfinished findings and the exact next action, in its own
  words.
- **Blockers** — any environment or tool failure that stopped it.

The orchestrator **consumes** that handoff on redispatch: the next agent
receives the completed set as done and starts at the named next action. It
never restarts the whole finding set. A budget overrun keeps the `BLOCKED`
disposition every stopped run carries; it is told apart by the
`writer stopped at its budget:` prefix on `unresolved_work[0]` (or
`budget checkpoint invalid:` when the checkpoint failed validation), so a run
that hit its ceiling is not mistaken for a run that broke.

The typed seam behind this is
`easy_cheese_schemas.workflow.WriterBudgetExceeded`, which carries a
`WriterCheckpoint` of those four parts; Blockers ride inside its `reason` text
next to the budget cause. The host finalizes it into a partial curd result
whose completed criteria keep their disposition and evidence and whose
unreached criteria are blocked on the overrun reason. Completed entries may
only report finished criteria (passed or failed) and are read in criterion
order, and a checkpoint that fails validation still salvages its readable
deliverables into the blocked result. A
checkpoint claiming every criterion is rejected: the review branch is skipped
on the overrun path, so full coverage would be a pass no reviewer ever saw.
