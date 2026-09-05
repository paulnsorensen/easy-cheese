---
name: cure
description: Apply selected fixes from an /age report, findings list, or CI failure. Run the project gates and hand a clean result to /plate. Use when the user wants selected findings resolved. Do not use for review, test authoring, or direct publication.
license: MIT
metadata: {dispatches-agents: true}
---

# /cure

Use this skill after `/age`, failed validation, or a request to fix selected review findings.

## Inputs

Accept an `/age` slug, a pasted findings list, a CI failure summary, or a scoped fix instruction.

`/cure <slug>` reads `.cheese/age/<slug>.md`.

Adopt a locked selection from `/age` or `/affinage`.
The canonical format is in `references/selection.md#handoff-from-age`.
Otherwise, apply the recommended composite from `references/selection.md`.
That file also defines the selection gate conditions.

Older Age reports can omit finding fields or `confidence`.
Read `references/selection.md` § Older report shape before you select from these reports.
Do not reject a report because it lacks these fields.

Optional flags:

- `--safe` — Restore the selection gate and the final publication gate.
- `--open-pr` — Permit `/plate` to publish when no PR exists.
- `--auto` — Use automatic mode from `/cook --auto`.
  Skip user selection.
  Require `--stake <floor>`.
  `/cook --auto` always passes `medium+`.
- `--stake <floor>` — Set the severity floor for `--auto`.
  Accept `blocker`, `high`, `medium+`, or `all`.
  Ignore this flag without `--auto`.
- `--hard` — Pass the metacognitive gate flag to `/plate`.

Read `references/selection.md` for selection rules.
Read `## Auto mode` for the pass cap and revert behavior.
Read `## --hard mode` for the metacognitive gate.

Read [`harness-portability.md`](../cheese/references/harness-portability.md) for portability rules.
Slash commands are host renderings, not the control model.

## Flow

1. **Load.** Read `handoff_context.source_report` first when the handoff supplies it.
   Confirm that the file exists and belongs to the named `source_skill`.
   Stop with `status: halt: unreadable source report` when this check fails.
   Read `.cheese/age/<slug>.md` when the handoff supplies only a slug.
   Take the typed path only when the handoff also supplies a `CurdPlan`.
   Call `validate_curd_plan` on that plan.
   Stop before dispatch when the plan or its digest is invalid.
   Do not rebuild a plan from a legacy manifest.
   Take the report path in every other case.
2. **Select.** Adopt a locked selection from `/age` or `/affinage`.
   Otherwise, apply the recommended composite.
   Read `references/selection.md` for verbs and gate conditions.
   Expand a user verb with this command:

   ```text
   python3 skills/cure/scripts/cure.pyz findings-cli parse-selection --report <path> --selection "<verb>"
   ```

   Use the same bundle command when the host only ships the bundle.
3. **Apply.** Fix one logical group at a time.
   Confirm each anchor with a fresh bounded read.
   The report path stops here and continues at step 4.
   The typed path also invokes `easy_cheese_schemas.cure` with the validated plan.
   Add one `CureDiagnosisBinding` for each selected curd.
   Create each binding with `bind_diagnosis(plan, curd, diagnosis_result)`.
   Use only a confirmed `DiagnosisResult`.
   Point the binding to the exact plan and curd digest.
   Set `DiagnosisDisposition.CONFIRMED`.
   A plausible but unrelated diagnosis does not unlock Cure.
   `cure` resolves each `ArtifactRef` with `resolve_artifact`.
   It accepts only observation-only `CurdResultWriterView` output.
   It uses `normalize_agent_output` to finalize one `CurdResult` per selected curd.
   It also finalizes executor failures.
4. **Validate.** Run the narrowest test that proves each fix.
   Then run the relevant project gates.
   These gates include lint, type checks, and builds.
   When the handoff has a `baseline:` block, use [`quality-gates.md`](../cook/references/quality-gates.md).
   Identical baseline failures do not block a clean cure or trigger a halt.
   Fix only new or changed failures.
5. **Taste-test behavioral fixes.** Run the fresh-context taste test before you write the handoff slug.
   Resolve the read-only `reviewer` phase agent through [`agent-resolution.md`](../cheese/references/agent-resolution.md).
   Request the powerful minimum power and high effort.
   Use the Cook review lenses over the cure diff.
   Halt when fresh-context isolation is unavailable.
   Use an inline self-check only under the small-diff cost gate in [`tdd-loop.md`](../cook/references/tdd-loop.md).
   Skip this step for formatting, comments, imports, and logic-free renames.
   Send a `revise` verdict into one bounded correction pass.
   Stop for a human on a Locked-decision `halt`.
   A nested coder defers the authoritative review to the orchestrator.
6. **Correct the domain model.** Correct only terms that the Cook diff touches.
   Read `references/domain-model-correction.md` first.
   Do not reverse a canonical term that Mold locked.
7. **Hand off for review.** Recommend `/age <slug> --scope <touched-path>`.
   Repeat `--scope` once for each touched path.
   Send the current slug with every Age dispatch.
   Forward `--hard` when the run has that flag.
   Do not duplicate the Age review inside Cure.
   A new Age report can start a new `/cure` run.
8. **Write the report.** Record changes, checks, deferred items, and residual risks.
   Put the handoff slug at the top of `.cheese/cure/<slug>.md`.
9. **Write back the durable facts.** Run § Post-PR write-back before publication.
   Give each written path to `/plate` for its artifact inventory.
10. **Hand off for publication.** Dispatch `/plate` after a clean cure.
    Follow `## Handoff`.

## Preferred tools and fallbacks

Route source work through [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md).
Use its fallback when a preferred tool is absent.
Stop only when the fallback cannot support a safe fix.
Report the precision loss.

## Validation

Run the narrowest test that proves each fix.
Then run all relevant existing gates.
Record why an unavailable gate cannot run.
Do not declare readiness while selected findings remain unresolved.

Move a finding to Applied only after its proving test passes.
Read `references/cure-discipline.md` for the Iron Law.

A **clean cure** has at least one applied fix and all gates pass.
It also has no false-premise halt.
Identical `baseline:` failures do not count against green status.
Read [`quality-gates.md`](../cook/references/quality-gates.md).

The agent judges the gate values.
The CLI maps those values to a readiness verdict:

```text
python3 skills/cure/scripts/cure.pyz gates-cli classify \
  --press-status <label> \
  [--hard-floor-met] [--has-open-level-1-or-2] [--has-open-level-3] [--has-open-level-4-or-5] [--any-spinning]
```

Use the same bundle command when the host only ships the bundle.

## Handoff slug

Write the report to `.cheese/cure/<slug>.md`.
Put this minimum handoff slug at the top:

```markdown
status: <canonical status field>
next: age | done
artifact: <path of the report that this run consumed>
baseline: none | <recorded baseline block copied from the upstream handoff — see ../cook/references/quality-gates.md>
<one-line orientation: what cure applied or deferred>
```

The [handback contract](../cheese/references/handback-contract.md) defines the `status:` grammar.
Only `next:` and the additional keyed lines are specific to this phase.
`artifact:` names the source report that this run consumed.
Use `handoff_context.source_report` for that value, or the resolved `.cheese/age/<slug>.md` path.

Write the report body to a separate file.
Then let the canonical writer create `.cheese/cure/<slug>.md` once.
Pass every optional field that this run has.

```text
python3 skills/cure/scripts/cure.pyz write-handoff-artifact \
  --slug <slug> --status <status> --phase cure --next age \
  --artifact <consumed-report-path> --orientation "<one-line orientation>" \
  --baseline "<copied baseline block>" --durable-flags "<one line per flag>" \
  --body-file <body-path> \
  --payload-schema https://schemas.easy-cheese.dev/curd-result
```

Use a second command for the terminal state.
Omit `--payload-schema`, because a terminal transition rejects a payload schema.

```text
python3 skills/cure/scripts/cure.pyz write-handoff-artifact \
  --slug <slug> --status <status> --phase cure --next done \
  --artifact <consumed-report-path> --orientation "<one-line orientation>" \
  --baseline "<copied baseline block>" --body-file <body-path>
```

Omit `--baseline` and `--durable-flags` when this run has no such value.
`phase=cure` controls storage routing.
`next` declares the following phase, and the writer validates that transition.

Use `status: ok` when at least one finding applies cleanly.
Use it when no finding meets the `--auto` severity floor.
Use `status: halt: <reason>` when every selected fix fails evaluation.
Use it when a project gate cannot pass.
Use `next: age` when review follows.
This value is the default for automatic and interactive runs.
Use `next: done` only for an interactive run without `--auto`.
The user must also decline review explicitly.
Cure does not track the current pass.
`/age --auto` enforces the two-cure-pass cap on its third invocation.

## Output

Use [`formatting.md`](../cheese/references/formatting.md).
Below the slug, add the exact headings `### Applied`, `### Deferred`, `### Checks`, and `### Re-review`.
Bind `<slug>` to the stem of the consumed source report.
When `source_skill` is `/affinage`, end each result line with `[from-comment:<id>]`.
Include finding IDs, evidence, residual risk, and the next command.
Use `/age <slug> --scope <touched-path>` or `/plate` as that command.

## Handoff

**Pipeline:** culture → mold → cook → press → age → **[cure]** → plate

After the report exists, decide whether to dispatch `/plate` or ask.
A clean cure updates an open PR without another gate by default.
`--safe` restores the handoff gate.

When `/affinage` started the run, never dispatch `/plate` from Cure.
This state uses `handoff_context.source_skill: /affinage`.
Apply the fixes and run the automatic Age loop when required.
Then return control to `/affinage`.
It posts the GitHub replies before it dispatches `/plate`.

**Default without `--safe`:**

- With an open PR, dispatch `/plate [--hard]`.
  It performs its final write gate, commit, topology update, and publication.
- With no open PR, use `--open-pr` to dispatch `/plate [--hard]`.
  In this case, explicit topology choices and obviously cohesive work proceed without asking.
  In other cases, stack-sized or ambiguous work asks before commit or branch-layout mutation.
- Without `--open-pr`, leave the remote unchanged.
  Report `no open PR — pass --open-pr or run /plate`.
- Run § Post-PR write-back before every `/plate` dispatch.
- Skip `/plate` when the cure is not clean.
  Report the blocker and stop.

With `--safe`, use the shared [handoff gate](../cheese/references/handoff-gate.md).
Offer these choices:

- **Review the touched code.** Run `/age <slug> --scope <touched-path>`.
  Recommend this choice when fixes extend beyond the finding hunk.
- **Plate it.** Run `/plate [--hard]` to commit and publish.
- **Checkpoint and stop.** Run `/wheypoint`.
- **Stop.** Dispatch nothing.

Preselect **Plate it** only when all selected fixes and gates pass.
Run the selected command immediately.

### Post-PR write-back

Read `references/post-pr-writeback.md` before any path publishes to a PR.
This includes default, `--open-pr`, `--safe`, and automatic publication paths.
The file defines candidates, writers, fallback behavior, ownership, and the empty case.

## --hard mode

`/cure --hard` passes `--hard` to `/plate`.
`/plate` completes and verifies every durable write.
It then gives `/hard-cheese` the final artifact inventory.
Stop publication on a `FAILED` gate result.
Stop publication when a non-TTY environment blocks the gate.
An `ERROR` result uses the hard-cheese fail-open policy, and publication continues.
Review, checkpoint, and stop choices skip this gate.
Read `skills/hard-cheese/SKILL.md` and `../hard-cheese/references/composition.md`.

## Auto mode

With `--auto --stake <floor>`, skip the selection list and handoff gate.
Select each finding that meets the floor.
Apply and validate each finding.
Revert and defer a finding when its test fails.
Then invoke `/age <slug> --scope <touched-path> [--scope <touched-path>] --auto`.
Forward `--open-pr` and `--hard` when they are in scope.
`/age --auto` owns the two-pass cap.
On `next: done`, run § Post-PR write-back.
Then dispatch `/plate` once.

Read `references/auto-mode.md` before you use this mode.
It defines the empty-floor case and the `--auto --hard` puncture clause.
It also defines Cook worker exceptions that suppress `/plate`.

## Rules

- Use the recommended composite or the locked selection by default.
  `--safe` restores the gate.
  Pause for false-premise, sprawling, structural, or conflicting findings.
- Keep fixes within the selected findings.
  Do not fix failures identical to the baseline.
- Report failed and skipped checks.
  Put reverted automatic findings under `### Deferred`.
- Follow `## Handoff` for every publication decision.
  Never publish an unclean cure.
- Stop before you apply a finding that rests on a false premise.
  Report why the Age claim is wrong or obsolete.
- Apply the shared voice rules from `../age/references/voice.md`.
  Lead with the applied changes.
  Mark residual risk as `certain | speculating | don't know`.
  Do not invent follow-up work for a correct diff.
- Identify the gate command before you claim `status: ok`.
  Run it again in the same turn.
  Read its full output.
  Then make the claim.
  Do not use `should`, `probably`, or `I think` in completion claims.
  State what the gate output shows.

## Discipline

Read `references/cure-discipline.md` before you apply any fix.
It defines the Iron Law, Red Flags, and rationalization table.

## Agent resolution

Resolve fix work through [`agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Apply selected findings | coder | write, isolated worktree | default | high | compatible coder, then general |

The canonical Cure handoff includes the shared `agent_resolution` block.

See the generated command inventory in [`references/commands.md`](references/commands.md).
