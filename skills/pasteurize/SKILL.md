---
name: pasteurize
description: >
  Diagnose and fix hard bugs. Build a reliable reproduction, name the cause,
  add a regression test, and apply the minimum fix.
license: MIT
---

# /pasteurize

Use this process for hard bugs.

Follow [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md) when you explore code.
Check `.cheese/specs/` for notes about the failed seam.

Read [`harness-portability.md`](../cheese/references/harness-portability.md) for portable tool use.
Use bundled or repository helpers before `${CLAUDE_SKILL_DIR}`.
Treat `${CLAUDE_SKILL_DIR}` as an optional host fallback.
Use the handoff blocks as the portable contract.
Remember that slash commands are host renderings, not the control model.

## Phase 1: Build the feedback loop

Build a fast and reliable pass-or-fail signal before you diagnose the bug.
This signal controls every later phase.

Read [`references/feedback-loops.md`](references/feedback-loops.md) for the ordered loop options.
Select the first option that reaches the failed seam.

Improve the loop before you continue.

- Reduce setup and unrelated initialization.
- Check the exact symptom.
- Control time, random values, files, and network access.

### Non-deterministic bugs

Increase the reproduction rate above 50 percent.
Repeat the trigger, add stress, narrow timing windows, or add controlled delays.

### No usable loop

Stop when you cannot build a usable loop.
List each method that you tried.
Request access to the reproduction environment.
Alternatively, request a captured artifact or permission for temporary production instrumentation.
Write a `status: halt` handoff slug.
Do not form hypotheses without a loop.

Confirm these conditions before Phase 2:

- [ ] The loop gives the same result each time.
- [ ] A flaky loop reproduces the bug more than 50 percent of the time.
- [ ] One command runs the loop without human action.
- [ ] The loop checks the exact reported symptom.
- [ ] The loop completes in less than 30 seconds.

Aim for a loop that completes in less than five seconds.

## Phase 2: Reproduce the bug

Run the loop five times.

```bash
python3 skills/pasteurize/scripts/pasteurize.pyz repro-rerun --cmd "<repro-command>" --runs 5
```

Confirm that the result contains `reproduced: true`.
Confirm that `failures` matches the expected failure mode.
Increase `--runs` when five runs do not reproduce a flaky bug.
Do not continue until the loop reproduces the bug.

## Symptom gate

Classify the symptom before you form hypotheses.

- Continue at the current model tier for a clean stack trace and a reliable loop.
- Upgrade the model tier for races, cross-module failures, performance regressions, or Heisenbugs.

Use the harness command for the model upgrade.
For Claude, use `/model opus` and `/effort`.
Use the named equivalent for Codex or OMP.
Use a generic model upgrade on other hosts.

## Phase 3: Form hypotheses

Write three to five ranked hypotheses before you test one.
State a testable prediction for each hypothesis.
Discard a hypothesis when you cannot state its prediction.

Use this format:

> If `<X>` causes the bug, then `<changing Y>` removes it or `<changing Z>` makes it worse.

Show the ranked list through [`handoff-gate.md`](../cheese/references/handoff-gate.md).
Domain knowledge can change the ranking.
Continue with your ranking when the user is unavailable or uses `--auto`.

## Phase 4: Add instrumentation

Map each probe to one Phase 3 prediction.
Change one variable at a time.

Use tools in this order:

1. Use a debugger or REPL when the environment supports it.
2. Add targeted logs at boundaries that distinguish hypotheses.
3. Do not log all data and search it later.

Prefix each temporary log with a unique tag such as `[DEBUG-a4f2]`.
Use the selected search backend to find every tagged log during cleanup.

For performance regressions, measure a baseline before you change code.
Use a timing harness, profiler, or query plan.
Then bisect the failed range.

## Phase 5: Fix the bug

Add the regression test before the fix.
Only add the test when a correct test seam exists.

A correct seam exercises the real bug at its actual call site.
It uses the real data path and failure mode.
A shallow or mocked seam gives false confidence.

Treat a missing seam as an architectural finding.
Record it in the handoff slug.
Write the applicable halt string.
Route the work to `/mold`.
Do not add a test at an incorrect seam.

When a correct seam exists, complete these steps:

1. Convert the minimum reproduction into a failing test at that seam.
2. Run the test and observe the failure.
3. Apply the smallest production change that can fix the failure.
4. Run the test and observe success.
5. Run the original Phase 1 loop and confirm that the symptom is absent.

Revert an unsuccessful fix before the next attempt.
Stop after three unsuccessful fix attempts.
Return to Phase 3 and write a new ranked hypothesis list.
Do not make a fourth attempt without a new hypothesis.

Restart at Phase 4 when you find a new hypothesis.
Otherwise, write the fix-attempts-exhausted halt string.
Then route the work to `/mold`.

Leave broader changes for `/cook`.
Record those changes in the handoff slug.

## Phase 6: Clean the worktree

Complete this checklist before you write the handoff slug:

- [ ] Run the original loop and confirm that the bug is absent.
- [ ] Run the regression test and confirm success.
- [ ] Record the missing test seam when no correct seam exists.
- [ ] Remove all `[DEBUG-...]` instrumentation.
- [ ] Delete temporary harnesses and prototypes.
- [ ] Record any retained debug file in the slug.
- [ ] Record the confirmed hypothesis in the slug.

Run the instrumentation sweep:

```bash
python3 skills/pasteurize/scripts/pasteurize.pyz debug-tag-sweep --root .
```

Exit status 0 means that the sweep found no tags.
Exit status 1 means that the sweep found listed tags.
Remove each listed tag before you continue.

Identify what could prevent this bug.
Record necessary architectural work in the slug.
Make this recommendation after you apply the fix.

Hand the completed slug to `/cook <slug> --auto`.
Cook checks the existing diff and runs the `press -> age -> cure` chain.
Pasteurize does not commit changes or open pull requests.

## Fan-out sizing

`/pasteurize` currently starts no agents.
`size_pasteurize_fanout()` defines a future policy in `src/easy_cheese/shared/fanout/pasteurize_route.py`.

The policy reads `review_surface` descending across the suspect range from the last known good revision to `HEAD`.
A lower evidence score produces more agents because it represents a larger search space.

| Bug shape | Range | Repro | Agents |
| --- | --- | --- | --- |
| regression | tight, score < 250 | deterministic | 1 |
| regression | tight, score < 250 | non-deterministic | 2 |
| regression | wide, score > 250 | deterministic | 2 |
| regression | wide, score > 250 | non-deterministic | 3 |
| regression | no score | deterministic | 3 |
| regression | no score | non-deterministic | 5 |
| race, heisenbug, or performance regression | any | any | 3 |
| cold bug | no score | deterministic | 3 |
| cold bug | no score | non-deterministic | 5 |

A score of 250 defines a tight range.

The constants are reasoned and not measured.
Reviewer thresholds use 30 repository commits, but these constants have no run history.
Keep the named constants adjustable.
Review them when real runs exist.

Bundle-only hosts can call the policy with this command:

```bash
python3 skills/pasteurize/scripts/pasteurize.pyz pasteurize-route <request.json>
```

The command reads JSON and writes JSON.
It follows the `age-route` bundle convention.

## Preferred tools

| Need | Preferred tool | Fallback |
| --- | --- | --- |
| Code search and impact | semantic caller and dependency search | bounded text search with a precision warning |
| Code read | fresh bounded read from the write backend | bounded read with stable line anchors |
| Instrumentation edit | stale-safe anchored edit | LSP or snapshot edit with stale-write detection |
| Diff view | `delta` | plain `git diff` |
| GitHub context | `gh` | local Git history or user links |
| External check | `/briesearch` | a clearly marked assumption |

Continue diagnosis when an optional tool is unavailable.

## Output

Return a short report with these items:

- The named cause and its confidence.
- The loop command and the observed result.
- The considered hypotheses and the confirmed hypothesis.
- The regression test path.
- The changed production lines.
- The instrumentation and temporary file cleanup status.
- The next command, `/cook <slug> --auto`.

Use `<certain>`, `<speculating>`, or `<don't know>` for confidence.

## Handoff slug

Write the handoff slug to `.cheese/pasteurize/<slug>.md`.
Use this minimum form:

```markdown
status: <canonical status field>
next: cook | mold | done
artifact: <path-to-richer-report-if-any>
cause: <one-sentence named cause>
loop: <command or repro path>
seam: <regression-test path:line, or "none — architectural follow-up">
fix: <production diff footprint, e.g. "src/foo.ts:42">
follow_up: <architectural follow-up note, or "none">
<one-line orientation: what pasteurize confirmed>
```

Use `status: ok` after the test, reproduction, and cleanup checks succeed.
Use `halt: <reason>` after an early-stop condition.
Follow the [handback contract](../cheese/references/handback-contract.md).

Set `next: cook` for the standard chain.
Set `next: mold` when the diagnosis requires an architectural specification.
Set `next: done` when an external cause needs no repository change.

## Handoff

**Pipeline:** cheese -> **pasteurize** -> cook --auto -> press -> age -> cure -> plate

After you write the report and slug, present these options through [`handoff-gate.md`](../cheese/references/handoff-gate.md):

- **Validate and continue:** `/cook <slug> --auto`.
- **Validate without the automatic chain:** `/cook <slug>`.
- **Specify the architectural work:** `/mold <slug>`.
- **Stop:** Leave the fix in the worktree.

Recommend the first option for `status: ok`.
Do not start an option without the user's selection.
Skip this question in `--auto` mode.

## Auto mode

`--auto` skips the Phase 3 ranking question.
It also skips the Phase 6 handoff question.
It starts `/cook <slug> --auto` after cleanup.
It does not skip Phase 4 or Phase 5.

### Early-stop conditions

Stop for any of these conditions:

- Phase 1 cannot produce a usable loop.
- Two Phase 3 rounds disprove all hypotheses.
- Phase 5 finds no correct regression-test seam.
- The minimum fix breaks an unrelated test outside the pasteurize scope.
- Three unsuccessful fixes exhaust all hypotheses.

For a missing seam, write `status: halt: no correct regression-test seam`.
For exhausted fixes, write `status: halt: fix attempts exhausted — architectural re-examination needed`.
Route both conditions to `/mold`.
Always write the halt slug and show the report.
Do not replace evidence with a best guess.

## Rules

- Do not skip Phase 1.
- Do not form hypotheses without a reproduction loop.
- Change only the regression test and the minimum production code in Phase 5.
- Remove every `[DEBUG-...]` tag before handoff.
- Do not claim that Pasteurize ships the change.
- Use this completion claim: "cause named, regression green, fix in tree, ready for chain".
- Record an architectural gap in the slug.

## References

- Generated bundle commands: [`references/commands.md`](references/commands.md).
