---
name: cook
description: >-
  Implement an approved spec or focused task through stale-safe source edits.
  Use this skill when the user says "implement this", "cook this spec", or "fix this bug".
  Use it for `/cook .cheese/specs/<slug>.md`.
  Also use it when the user says "go" or "ship it" with clear acceptance criteria.
  Run it alone for an unambiguous task.
  A spec helps but is not required.
  Do not use it for fuzzy planning (`/mold`).
  Do not use it for no-write discussion (`/culture`) or review-only work (`/age`).
license: MIT
metadata: {dispatches-agents: true}
---

# /cook

## Contract

`cook(spec_ref, correction = false) -> handoff(next = press | age | mold)`.

Cook returns `next: mold` only for a specification failure.

A `red-required` gate disposition identifies behavior work.
Run the inner RED → GREEN TDD loop against the approved spec before you change production code.
A closed `not-applicable` disposition identifies non-behavior work.
Use its implementation and verification path for the requested documentation, refactor, test, or appearance change.
N/A does not remove requested work.
Use `correction = true` only for the active Press correction loop.
Do not weaken an existing test.

## Inputs

Accept a pasted spec or issue, focused acceptance criteria, or an unambiguous task.
Read explicit spec paths verbatim.
Resolve a bare slug with `SPEC=$(python3 skills/cook/scripts/cook.pyz artifact-path specs <slug>)`.
Use `python3 skills/cook/scripts/cook.pyz accept <pointer>` for a Mold handoff pointer.
This command verifies the route and referenced artifacts before execution.

Flags:

- `--auto` chains `/press → /age → /cure`.
- `--hard` propagates through `/plate`.
- `--open-pr` lets terminal `/plate` publish. Auto mode never adds this flag.
- `--resume <slug>` resumes a typed fan handoff and its referenced artifacts.

Optional context payload:

- `handoff_context.wiki_hits` carries `{page, line, why}` entries from the repository wiki corpus.
  The key is optional, and its default is absent.
  Reject an entry that omits `page`, `line`, or `why`.
  Show every accepted hit in the **Contract** step, so the user can challenge a stale decision.
  Prefer these decisions over an invented approach.
  [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md) defines the payload.

Read `references/auto-mode.md`, `references/fan-pathway.md`, and `../cheese/references/formatting.md` for these policies.

### Standalone fast-path

`/cook` bypasses `/mold` only when the inputs, outputs, scope, and verification are clear.
The task must name a bug or call site in one or two files.
The task must also have a failing test or an expected-output check.
Derive a slug.
Then restate the **Contract**.
Route the task to `/mold` if an ambiguity check fails.

## Flow

1. **Contract** — Confirm behavior, non-goals, scope, gates, and applicability.
   If `.cheese/glossary/<slug>.md` exists, use its canonical terms.
2. **Implement** — Use inner RED → GREEN for behavior changes.
   Use the requested non-behavior path for closed N/A work.
   Change only the applicable surface.
3. **Validate** — Run the relevant quality gates again.
   Read the complete gate output.
   For closed N/A, verify the requested non-behavior path.
4. **Taste-test** — Use a fresh-context review for multi-file or public-surface diffs.
   Otherwise, use an inline review.
   Limit the review to two rounds.
   Read `references/tdd-loop.md` for details.
5. **Hand off** — Write the package report and slug.
   Route behavior work through `/press → /age → /cure`.
   A closed N/A change has no adversarial contract for Press.
   Route it directly through `/age → /cure`.

## Fan pathway

`/cook` routes a spec through one of three shapes.
The available typed planner result selects the shape.
Read [`references/fan-pathway.md`](references/fan-pathway.md) for the complete topology.

**Fast path.** Use the ordinary single-coder path when the curd-count hint is `1` with low or medium blast radius.

**Curded.** Load the typed `PlannerResult` or `CurdPlan`.
Run `validate_curd_plan`.
Treat the validated plan as the semantic authority.
Run behavior curds through `cook(CurdPlan) → reviewer(age) → cure(CurdPlan, binding) → reviewer(final age)` without Press.
After you wire the curds, run one global `/press → /age → /cure` chain.
Closed N/A bypasses Press.

Use `python3 skills/cook/scripts/cook.pyz worktree teardown` for worktree cleanup.
The fan-pathway reference defines its arguments and lifecycle.

**Un-curded.** Keep small work in the single-coder path.
For big work, ask "12 ACs -> 5 curds, 2 waves, up to 25 agent dispatches. Go?" unless `--auto`.
Keep waves at a maximum of four.
Legacy decomposition is only a lossless projection.
It is never live workflow state.
Follow [`decomposer.md`](../cheese/references/decomposer.md) for sizing and decomposition.

Before orchestration, read [`references/fan-pathway.md`](references/fan-pathway.md).
It defines sizing, topology, phase execution, recovery, resume, Milknado integration, worktree teardown, and resolution provenance.
Propagate `--auto` through each dispatched phase when it is active.

## Baseline capture

Fan mode records its quality-debt comparison before any curd cooks.
Bare mode records it on the pre-change tree.
[`references/quality-gates.md`](references/quality-gates.md) defines exact capture, classification, intentional-RED exclusion, and baseline-artifact rules.

For source changes, follow [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md) and [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md).
`slash commands are host renderings, not the control model`; invoke the equivalent installed capability.

## Quality gates

Run only existing project commands.
Run the most relevant tests for the changed area.
Also run lint, type, and build commands when the project defines them.
Do not remove, skip, or weaken unrelated tests to make the change pass.

Use the baseline for gate failures.
[`references/quality-gates.md`](references/quality-gates.md) defines the policy, the classification terms, and the baseline artifact.
Each downstream phase links to this reference instead of repeating it.

[`references/writer-views.md`](references/writer-views.md) generates schemas for writer-view payloads inline.
The `normalize` and `validate` CLIs apply these schemas before agent-authored JSON reaches host-owned identifiers.

## Output

Use the house style in [`../cheese/references/formatting.md`](../cheese/references/formatting.md).
Use [`references/package-report.md`](references/package-report.md) to report files, reasons, checks, risks, and the next skill.

## Handoff slug

Write a minimum-shape handoff slug at the top of `.cheese/cook/<slug>.md`.
Use the same file for the report.
Do not create a second file.
This slug lets downstream phases resume or chain without reading the full report again.
The fan pathway also uses this slug during wave orchestration.
Use this schema:

```markdown
status: <canonical status field>
next: mold | cook | press | age | done
artifact: <path to the upstream artifact this run consumed, or empty>
taste_test: inline-pass | dispatched-pass | revised | deferred-to-orchestrator
durable_flags: none | <one line per flag: what durable knowledge changed -> target wiki page>
baseline: none | <path to the baseline artifact — shape in references/quality-gates.md § Baseline block shape>
<one-line orientation: what cook changed>
```

The [handback contract](../cheese/references/handback-contract.md) defines the canonical `status:` grammar, including `ok` and `halt`.
Only `next:` and the additional keyed lines are specific to a phase.

`artifact:` names the upstream artifact that this run consumed.
For a Mold route, use the approved specification pointer.
Leave `artifact:` empty when this run consumed no upstream artifact.
Do not point `artifact:` at this Cook report.
`/cheese` forwards the same pointer to the next phase.

Use the canonical boundary writer when you emit this handoff for the typed fan result.
Carry the result schema explicitly:

```text
python3 skills/cook/scripts/cook.pyz write-handoff-artifact \
  --slug <slug> --status <status> --phase cook --next age \
  --artifact <artifact-path> --orientation "<one-line orientation>" \
  --payload-schema https://schemas.easy-cheese.dev/curd-result \
  --body-file <path to the package report body>
```

The writer replaces the target file.
Pass `--body-file` to keep the package report in the same file.
Without that flag, the writer emits the preamble alone and removes the report.

For a replan or a specification failure, use `--next mold` with the `https://schemas.easy-cheese.dev/planner-request` payload.
[`references/fan-pathway.md`](references/fan-pathway.md) defines the request kind for each failure class.
These `phase` and `next` values route only the legacy handoff file.
The validated `CurdPlan` and normalized `CurdResult` remain the live fan state.

In a fan run, read each phase's handoff slug file from disk.
Do not infer the handoff from stdout.

Set `next:` to the next runnable phase.
Use `press` after red-required behavior work.
Use `age` after closed N/A.
Use `cook` after a blocker.
Use `mold` after a spec failure.
Use `done` only at true completion.
Do not send contractless N/A to Press.
Omit `taste_test:` when its cost gate does not apply.

Set `durable_flags:` to `none` by default.
Record only durable changes to architecture, protocols, conventions, or rationale.
Record the target wiki page for each change.
Set `baseline:` to the path of Cook's optional comparison artifact.
That artifact holds baseline-identical debt and new or changed failures from the current broad gates.
Use the shape in [`references/quality-gates.md`](references/quality-gates.md).
The preamble accepts one physical line for each key, so never inline the mapping.

## Handoff

**Pipeline:** culture → mold → cook → press → age → cure → plate

After you write the report and slug, use the shared handoff gate.
Read its **Standard forward-step menu** in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md).
For behavior work, start each option with the verb.
Use these options:

- **Harden tests before review** *(recommended)* — `/press <slug>`.
- **Plate it** — `/press <slug> --auto --open-pr`: run the remaining review chain, then `/plate` resolves topology and publishes.

Press does not apply to closed N/A.
Set `next: age`.
Replace the options with **Review the change** *(recommended)* — `/age <slug>`.
Also offer **Plate it** — `/age <slug> --auto --open-pr`.

Both menus retain **Checkpoint & stop** — `/wheypoint` and **Stop** — dispatch none.
Do not dispatch before selection.
Run the selected command immediately.
When the user invokes `--auto`, skip this gate.
Take the route for the applicable disposition directly.

## Auto mode

`--auto` does not bypass applicable validation.
Run behavior work through `/press --auto → /age --auto → /cure --auto --stake medium+`.
Closed N/A skips Press.
Run it through `/age --auto → /cure --auto --stake medium+`.
Limit Cure to two passes on both routes.
In the linear chain, Cook does not invoke `/plate`.
Terminal Cure then owns publication.
In the fan pathway, the Cook orchestrator owns its own terminal `/plate` dispatch.
[`references/fan-pathway.md`](references/fan-pathway.md) defines that dispatch.

Auto mode stops early in these conditions:

- A quality gate reports a new or changed failure, and the fix rounds end.
- The no-progress check stops the run.
- The fix requires a design change.
- `/press` returns `blocked`.
- A Cure pass cannot apply a finding.
- Two Cure passes complete the success path.

For each early stop, show the failing skill report.
State which limit or blocker stopped the run.
Do not silently downgrade the result.

Read [`references/auto-mode.md`](references/auto-mode.md) before you run or dispatch auto mode.
It defines the complete phase chain and the limit controls.
It also defines fan-path isolation and Cure failure handling.

## No-chain isolation directive

A spawned phase agent does not chain forward by itself.
The orchestrator controls the chain.

A terminal Age is publishable only with `next: done`.
`next: cure` or a missing `next` halts the chain.
The reference also contains the final report template.

## Rules

- Keep changes scoped to the accepted contract.
- Prefer existing dependencies and patterns.
- Do not invent architecture that the spec already rejected.
- Stop when implementation reveals a design decision that the spec does not answer.
- Ask the user that decision before you continue.
- Stop if the spec or fast-path request uses a false premise.
- Show the false premise before you write code.
- Do not use an incorrect approach to satisfy the request literally.
- Apply the shared voice kernel in `../age/references/voice.md`.
- Start the report with the answer.
- Name loaded assumptions in the contract.
- Mark residual risk as `certain | speculating | don't know`.
- **Verification before `status: ok`:** Identify the gate command.
- Run the gate command during the current turn.
- Read the complete output before you make the claim.
- Do not use `should`, `probably`, or `I think`.
- State what the gate output shows.

## Discipline

Iron Law, Red Flags, and the TDD Rationalization table are in [`references/cook-discipline.md`](references/cook-discipline.md).

## Agent resolution

Resolve through [`agent-resolution.md`](../cheese/references/agent-resolution.md).
Implementation uses a coder.
Taste-test uses a reviewer.
Harvest and plate stay parent-owned.

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Decompose the spec | planner, general | write (manifest only), fresh-context | powerful | high | compatible planner, then general |

The handoff carries the `agent_resolution` block.
Publish a terminal Age only when it contains `next: done`.
Stop when it contains `next: cure` or does not contain `next`.

Generated bundle command inventory: [`references/commands.md`](references/commands.md).
