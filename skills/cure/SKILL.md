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
- `--auto` — Use autonomous mode from `/cook --auto`.
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
slash commands are host renderings, not the control model.

## Flow

1. **Load.** Read the Markdown findings and the upstream typed `PlannerResult` artifact.
   Extract its `CurdPlan`.
   Call `validate_curd_plan`.
   Stop before dispatch if the plan or its digest is absent or invalid.
   Do not rebuild a plan from a legacy manifest.
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
   Invoke `easy_cheese_schemas.cure` with the validated plan.
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
   Dispatch the read-only `reviewer` phase agent over the cure diff.
   Use the Cook review lenses and the pinned Opus model.
   Use the inline self-check if that agent is unavailable.
   Skip this step for formatting, comments, imports, and logic-free renames.
   Send a `revise` verdict into one bounded correction pass.
   Stop for a human on a Locked-decision `halt`.
   A nested coder defers the authoritative review to the orchestrator.
6. **Correct the domain model.** Correct only terms that the Cook diff touches.
   Read `references/domain-model-correction.md` first.
   Do not reverse a canonical term that Mold locked.
7. **Hand off for review.** Recommend `/age --scope <touched-path>`.
   Do not duplicate the Age review inside Cure.
   A new Age report can start a new `/cure` run.
8. **Write the report.** Record changes, checks, deferred items, and residual risks.
   Put the handoff slug at the top of `.cheese/cure/<slug>.md`.
9. **Hand off for publication.** Dispatch `/plate` after a clean cure.
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

A finding is Applied only after its proving test passes.
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
artifact: <path-if-any>
baseline: none | <recorded baseline block copied from the upstream handoff — see ../cook/references/quality-gates.md>
<one-line orientation: what cure applied or deferred>
```

The [handback contract](../cheese/references/handback-contract.md) defines the `status:` grammar.
Only `next:` and the additional keyed lines are specific to this phase.

Write the legacy projection with the canonical writer.
Carry the typed Cure result schema across the boundary:

```text
python3 skills/cure/scripts/cure.pyz write-handoff-artifact \
  --slug <slug> --status <status> --phase cure --next age \
  --artifact <artifact-path> --orientation "<one-line orientation>" \
  --payload-schema https://schemas.easy-cheese.dev/curd-result
```

`phase=cure` and `next=age` control storage routing only.
The live state remains the validated `CurdPlan`, `CurdResult`, and `CureDiagnosisBinding` values.

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
Below the slug, add `Applied`, `Deferred`, `Checks`, and `Re-review` sections.
Include finding IDs, evidence, residual risk, and the next command.
Use `/age --scope <touched-path>` or `/plate` as that command.

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
- After publication, run § Post-PR learnings write-back.
- Skip `/plate` when the cure is not clean.
  Report the blocker and stop.

With `--safe`, use the shared [handoff gate](../cheese/references/handoff-gate.md).
Offer these choices:

- **Review the touched code.** Run `/age --scope <touched-path>`.
  Recommend this choice when fixes extend beyond the finding hunk.
- **Plate it.** Run `/plate [--hard]` to commit and publish.
- **Checkpoint and stop.** Run `/wheypoint`.
- **Stop.** Dispatch nothing.

Preselect **Plate it** only when all selected fixes and gates pass.
Run the selected command immediately.

### Post-PR learnings write-back

Read `references/post-pr-writeback.md` after any path publishes to a PR.
This includes default, `--open-pr`, `--safe`, and automatic publication paths.
The file defines candidates, writers, fallback behavior, ownership, and the empty case.

## --hard mode

`/cure --hard` passes `--hard` to `/plate`.
`/plate` completes and verifies every durable write.
It then gives `/hard-cheese` the final artifact inventory.
Publication continues only after a pass.
Review, checkpoint, and stop choices skip this gate.
Read `skills/hard-cheese/SKILL.md` and `../hard-cheese/references/composition.md`.

## Auto mode

With `--auto --stake <floor>`, skip the selection list and handoff gate.
Select each finding that meets the floor.
Apply and validate each finding.
Revert and defer a finding when its test fails.
Then invoke `/age --scope <touched-paths> --auto`.
Forward `--open-pr` when it is in scope.
`/age --auto` owns the two-pass cap.
On `next: done`, dispatch `/plate` once.
Then run § Post-PR learnings write-back.

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
