---
name: cure
description: Apply fixes from an /age report, finding list, or CI failure, then run the project's test/lint/build gates and hand a clean cure to /plate for commit/publication. Use when the user wants selected findings resolved. Do NOT use for review (route to /age), test authoring (route to /press), or direct publication (route to /plate).
license: MIT
metadata: {dispatches-agents: true}
---

# /cure

Use this skill after `/age`, failed validation, or user-selected review findings need to be fixed and prepared for shipping.

## Inputs

Accept any of: a `/age` slug (`/cure <slug>` reads `.cheese/age/<slug>.md`), a pasted findings list, a CI failure summary, or a scoped instruction like "fix the high-severity age findings". When `/age` or `/affinage` hands off a pre-locked selection (canonical format: `references/selection.md#handoff-from-age`), adopt it and go straight to apply. Called bare, apply the recommended composite (`all-medium, cheap`) per `references/selection.md`, which also defines the gate conditions.

Age reports may predate the severity-rubric revision and lack per-finding sub-fields or `confidence`. Read `references/selection.md` § Older report shape before selecting from such a report — it defines the inference and toleration rules; never reject a report for missing sub-fields.

Optional flags:

- `--safe` — re-introduce the selection and terminal publication handoff gates.
- `--open-pr` — after a clean cure, allow terminal `/plate` publication when no PR exists.
- `--auto` — autonomous mode (propagated from `/cook --auto`). Skips user selection; requires `--stake <floor>`, and `/cook --auto` always passes `medium+`. Auto-selection rules: `references/selection.md`; pass-cap and revert behaviour: `## Auto mode` below.
- `--stake <floor>` — with `--auto` only, ignored otherwise. Severity floor: `blocker`, `high`, `medium+`, or `all`; definitions and the `medium+` cheap-lows rule live in `references/selection.md` § Auto-mode selection.
- `--hard` — propagate the metacognitive-gate flag to terminal `/plate`; see `## --hard mode`.

Portability: [`harness-portability.md`](../cheese/references/harness-portability.md);
slash commands are host renderings, not the control model.

## Flow

1. **Load** — read the findings (markdown, not JSON sidecars) and load the
   upstream typed `PlannerResult` artifact. Extract its `CurdPlan` and call
   `validate_curd_plan`; if the plan or its digest is absent or invalid, stop
   before dispatch. Cure never reconstructs a plan from a legacy manifest.
2. **Select** — adopt any pre-locked handoff from `/age`/`/affinage`; otherwise apply the recommended composite. See `references/selection.md` for the default rule, recognized verbs, and gate conditions. To expand a user-supplied verb to finding ids:

   ```
   python3 shared/scripts/findings_cli.py parse-selection --report <path> --selection "<verb>"
   ```

   If the host only ships the bundle, `python3 ${CLAUDE_SKILL_DIR}/scripts/common.pyz findings_cli parse-selection ...` is the fallback.
3. **Apply** — fix one logical group at a time: re-confirm the anchor through
   a fresh bounded read, then invoke `easy_cheese_schemas.cure` with the
   validated plan and a `CureDiagnosisBinding` for every selected curd. Each
   binding must come from a confirmed `DiagnosisResult` passed to
   `bind_diagnosis(plan, curd, diagnosis_result)`, point to that exact plan/curd
   digest, and carry `DiagnosisDisposition.CONFIRMED`;
   an unrelated or merely plausible confirmed diagnosis does not unlock Cure.
   `cure` resolves each `ArtifactRef` with `resolve_artifact`, accepts only
   observation-only `CurdResultWriterView` output, and uses
   `normalize_agent_output` to host-finalize exactly one `CurdResult` per
   selected curd, including executor failure.
4. **Validate** — run the narrowest tests that prove each fix, then any relevant project-wide gates (lint, typecheck, build). When the handoff carries a recorded `baseline:` block, classify gate failures against it per [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md): identical failures do not block a clean cure or trigger a halt; only new or changed failures are cure's to fix.
5. **Taste-test (behavioural fixes only)** — for a *behavioural* fix (production logic or public surface), run the fresh-context taste-test before the handoff slug: dispatch the read-only `reviewer` phase-agent (model pinned to opus) over the cure diff with cook's lenses, or fall back to the inline self-check if unavailable. *Mechanical* fixes (formatting, comment, import, no-logic rename) skip this. Pipe a `revise` into a bounded corrective pass; a Locked-decision `halt` stops for a human. (A coder-nested cure defers the authoritative pass to the orchestrator.)
6. **Domain-model correction (diff-touched terms only)** — after the cook's fixes land, correct diff-touched domain-model terms (never a free rewrite). Read `references/domain-model-correction.md` before this step — it defines the store resolution, the entry format, and the hard rule against reversing a mold-locked canonical term.
7. **Re-review hand-off** — recommend `/age --scope <touched-path>` so review runs through the proper skill rather than reimplementing it inline. `/cure` does not re-grade its own work. If the user picks re-age, the resulting report can feed a fresh `/cure` invocation.
8. **Ship report** — what changed, checks run, deferred items, residual risks. Write the handoff slug at the top of `.cheese/cure/<slug>.md` (see `## Handoff slug` below) so the chain (and `/cook`'s fan pathway) can read the outcome without re-parsing the full report.
9. **Plate / hand off** — on a clean cure, dispatch `/plate` per `## Handoff`.

## Preferred tools and fallbacks

Route source reads, searches, and edits through
[`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md).
Use the documented fallback when a preferred tool is absent; stop only when the
fallback cannot support a safe fix, and report the precision loss.

## Validation

Run the narrowest tests that prove the fix, then any relevant existing wider gates. If a gate is unavailable, record why. Do not declare ready when selected findings remain unresolved.

Applied requires its proving test green (Iron Law — see `references/cure-discipline.md`).

**clean cure** — ≥1 fix applied, all gates green (identical recorded `baseline:` failures don't count against green — see [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md)), no false-premise halt. To map the post-cure gate booleans to a readiness verdict (agent judges the booleans; the CLI maps them):

   ```
   python3 shared/scripts/gates_cli.py classify \
     --press-status <label> \
     [--hard-floor-met] [--has-open-level-1-or-2] [--has-open-level-3] [--has-open-level-4-or-5] [--any-spinning]
   ```

   If the host only ships the bundle, `python3 ${CLAUDE_SKILL_DIR}/scripts/common.pyz gates_cli classify ...` is the fallback.

## Handoff slug

Write the cure report to `.cheese/cure/<slug>.md` with a minimum handoff slug at the top so `/cook`'s fan pathway and `/cheese --continue` can chain without re-parsing the full report:

```markdown
status: ok | halt: <one-line reason>
next: age | done
artifact: <path-if-any>
baseline: none | <recorded baseline block copied from the upstream handoff — see ../cook/references/quality-gates.md>
<one-line orientation: what cure applied or deferred>
```

Write that legacy handoff projection through the canonical writer, carrying the
typed Cure result schema at the boundary:

```text
python3 shared/scripts/write_handoff_artifact.py \
  --slug <slug> --status <status> --phase cure --next age \
  --artifact <artifact-path> --orientation "<one-line orientation>" \
  --payload-schema https://schemas.easy-cheese.dev/curd-result
```

The `phase=cure` directory and `next=age` transition are storage routing only;
the live Cure state remains the validated `CurdPlan`, `CurdResult`, and
`CureDiagnosisBinding` values above.

`status: ok` when at least one finding applied cleanly (or no findings met the severity floor in `--auto` mode); `status: halt: <reason>` when every selected fix failed the revert/keep evaluation or a project-wide gate cannot be made green. `next:` is `age` whenever re-review should follow — that is the autonomous-chain default and the standard interactive recommendation. `next:` is `done` only when invoked interactively without `--auto` *and* the user explicitly opts out of re-review. Cure does not track which pass it is on; the two-cure-pass cap is enforced by `/age --auto`'s third invocation, not by cure.

## Output

Use [`formatting.md`](../cheese/references/formatting.md). Below the handoff slug
in `.cheese/cure/<slug>.md`, record `Applied`, `Deferred`, `Checks`, and
`Re-review` sections with finding IDs, evidence, residual risk, and the next
`/age --scope <touched-path>` or `/plate` step.

## Handoff

**Pipeline:** culture → mold → cook → press → age → **[cure]** → plate

After the cure report is rendered, cure decides whether to dispatch `/plate` or ask. On a **clean cure** (see Validation), the default carries work to an already-open PR without another gate. `--safe` re-introduces the handoff gate.

When the run was chained from `/affinage` (`handoff_context.source_skill: /affinage`), cure **never** dispatches `/plate` — it applies its fixes, runs the auto-mode `/age --scope` loop where applicable, and returns so `/affinage` can post its GitHub replies (final writes) before owning terminal `/plate`.

**Default (no `--safe`) — plate the work:**

- With an open PR (`gh pr view`), dispatch `/plate [--hard]` for its final writing gate, commit, topology-aware update, and publication (Rule 11 authorizes the update).
- With no open PR: `--open-pr` dispatches `/plate [--hard]` — explicit topology choices and obviously cohesive work proceed without asking, while stack-sized or ambiguous work asks before commit or branch-layout mutation. Without `--open-pr`, leave the remote untouched and finish with `no open PR — pass --open-pr or run /plate`.
- After publication lands, run **§ Post-PR learnings write-back** below.
- If the cure was not clean, skip `/plate`; mention the blocker and stop.

**`--safe` — ask via the shared handoff gate** in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md). Default options:

- **Re-review the touched code** *(recommended when fixes escaped the finding hunk)* — `/age --scope <touched-path>`.
- **Plate it — commit and open or update the PR** — `/plate [--hard]`.
- **Checkpoint & stop** (`/wheypoint`) or **Stop** (dispatch none).

Pre-select **Plate it** only when all selected findings applied cleanly and gates passed. Never dispatch before selection; run the selected command immediately.

### Post-PR learnings write-back

After any path that **publishes to a PR** — the default `/plate` dispatch, an `--open-pr` new PR, the `--safe` **Plate it** selection, or the auto-mode terminal publication — read `references/post-pr-writeback.md` before writing back. It defines the write-back candidates (upstream `durable_flags` + new-since-curdle ADRs), the `/wiki-ingest` writer with its file-fallback degrade, the publication-owner exception, and the "nothing to record" case.

## --hard mode

`/cure --hard` propagates `--hard` to `/plate`, which completes and verifies every durable write, then gives `/hard-cheese` the final artifact inventory and proceeds only on pass. Re-review, checkpoint, and stop choices skip the gate. Mechanism: `skills/hard-cheese/SKILL.md`; composition: `../hard-cheese/references/composition.md`.

## Auto mode

When invoked with `--auto --stake <floor>`, skip the selection list and the handoff gate, auto-select every finding meeting the severity floor (`references/selection.md` § Auto-mode selection), apply and validate each one — reverting and deferring on breakage — then invoke `/age --scope <touched-paths> --auto` (forwarding `--open-pr` when in scope) so the chain re-reviews; `/age --auto` owns the two-pass cap. On a terminal `next: done`, dispatch `/plate` once and run the **§ Post-PR learnings write-back** above.

Read `references/auto-mode.md` before running this mode — it defines the empty-floor case, the `--auto --hard` puncture clause, and the cook fan-pathway sub-agent exceptions (single-curd chain and wave-curd worker) that suppress terminal `/plate`.

## Rules

- Default to the recommended composite (or `/age`/`/affinage`'s locked selection); `--safe` re-introduces the gate. A false-premise or sprawling/structural finding still pauses for a decision regardless of mode.
- Keep fixes scoped to selected (or auto-selected) findings. Baseline-identical gate failures are never cure's to fix (Flow step 4).
- Do not hide failed or skipped checks. In auto mode, reverted findings go under `### Deferred`, never silently dropped.
- Publication contract — existing PR authorization, `--open-pr`, `--safe`, and never publishing an unclean cure: see `## Handoff`.
- If a selected finding rests on a false premise (the `/age` claim is wrong, or the diff already addresses it), stop and surface the premise before applying. Disagreeing with the report is allowed; silently working around it is not.
- Apply the shared voice kernel (lives at `../age/references/voice.md`): lead the cure report with what was applied, flag residual risk as `certain | speculating | don't know`, agree when the diff is fine without manufacturing follow-ups.
- **Verification before `status: ok`:** before writing `status: ok` in the handoff slug, (1) identify the gate command, (2) run it fresh in the same turn, (3) read the full output, (4) only then claim. Hedging words (`should`, `probably`, `I think`) are banned in completion claims — state what the gate output showed, not what you expect it to show.

## Discipline

Read `references/cure-discipline.md` before applying any fix — it holds the
Iron Law, Red Flags, and the fix-application Rationalization table.

## Agent resolution

Resolve fix application through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Apply selected findings | coder | write, isolated-worktree | default | high | compatible coder, then general |

The canonical cure handoff carries the shared `agent_resolution` block.
