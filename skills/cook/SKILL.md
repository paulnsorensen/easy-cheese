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

`cook(spec_ref, correction = false) -> handoff(next = press | age)`.
A `red-required` gate disposition identifies behavior work.
Run the inner RED → GREEN TDD loop against the approved spec before you change production code.
A closed `not-applicable` disposition identifies non-behavior work.
Use its implementation and verification path for the requested documentation, refactor, test, or appearance change.
N/A does not remove requested work.
Use `correction = true` only for the active Press correction loop.
Do not weaken an existing test.

## Inputs

Accept a pasted spec/issue, focused acceptance criteria, or an unambiguous task.
Read explicit spec paths verbatim. Resolve a bare slug with
`SPEC=$(python3 skills/cook/scripts/cook.pyz artifact-path specs <slug>)`.
Use `python3 skills/cook/scripts/cook.pyz accept <pointer>` for a Mold handoff pointer.
This command verifies the route and referenced artifacts before execution.

Flags:

- `--auto` chains `/press → /age → /cure`.
- `--hard` propagates through `/plate`.
- `--open-pr` lets terminal `/plate` publish.
- `--resume <slug>` resumes a typed fan handoff and its referenced artifacts.

Read `references/auto-mode.md`, `references/fan-pathway.md`, and `../cheese/references/formatting.md` for these policies.

### Standalone fast-path

`/cook` bypasses `/mold` only when the inputs, outputs, scope, and verification are clear.
The task must name a bug or call site in one or two files.
The task must also have a failing test or an expected-output check.
Derive a slug.
Then restate the **Contract**.
Route the task to `/mold` if an ambiguity check fails.

## Flow

1. **Contract** — confirm behavior, non-goals, scope, gates, and applicability.
   If `.cheese/glossary/<slug>.md` exists, use its canonical terms.
2. **Implement** — use inner RED → GREEN for behavior changes.
   Use the requested non-behavior path for closed N/A work.
   Change only the surface that applies.
3. **Validate** — run the relevant quality gates fresh and read the output.
   For closed N/A, verify the requested non-behavior path.
4. **Taste-test** — use a fresh-context review for multi-file or public-surface diffs.
   Otherwise, use an inline review.
   Limit the review to two rounds.
   Read `references/tdd-loop.md` for details.
5. **Hand off** — write the package report and slug.
   Route behavior work through `/press → /age → /cure`.
   A closed N/A change has no adversarial contract for Press.
   Route it directly through `/age → /cure`.

## Fan pathway

`/cook` routes a spec through one of three shapes.
The available typed planner result selects the shape.
Read [`references/fan-pathway.md`](references/fan-pathway.md) for the complete topology.

**Fast path.** When the curd-count hint is `1` with low or medium blast radius,
use the ordinary single-coder path.

**Curded.** Load the typed `PlannerResult` or `CurdPlan`.
Run `validate_curd_plan`.
Treat the validated plan as the semantic authority.
Run behavior curds through `cook(CurdPlan) → reviewer(age) → cure(CurdPlan, binding) → reviewer(final age)` without Press.
After you wire the curds, run one global `/press → /age → /cure` chain.
Closed N/A bypasses Press.

Worktree cleanup uses `python3 skills/cook/scripts/cook.pyz worktree teardown`; the fan-pathway reference owns its arguments and lifecycle.

**Un-curded.** Small work stays single-coder. Big work asks
"12 ACs -> 5 curds, 2 waves, up to 25 agent dispatches. Go?" unless `--auto`.
Waves remain capped at four. Legacy decomposition is a lossless projection
only, never live workflow state.
Sizing and decomposition follow
[`decomposer.md`](../cheese/references/decomposer.md).

Before orchestration, read [`references/fan-pathway.md`](references/fan-pathway.md).
It defines sizing, topology, phase execution, recovery, resume, Milknado integration, worktree teardown, and resolution provenance.
Propagate `--auto` through each dispatched phase when it is active.

## Baseline capture

Fan mode records its quality-debt comparison before any curd cooks;
bare mode records it on the pre-change tree.
Exact capture, classification, intentional-RED exclusion, and
`manifest.yaml` rules live in
[`references/quality-gates.md`](references/quality-gates.md).

For source changes, follow
[`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md)
and [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md).
`slash commands are host renderings, not the control model`; invoke the
equivalent installed capability.

## Quality gates

Run only existing project commands.
Run the most relevant tests for the changed area.
Also run lint, type, and build commands when the project defines them.
Do not remove, skip, or weaken unrelated tests to make the change pass.

Gate failures use the baseline.
[`references/quality-gates.md`](references/quality-gates.md) defines the policy, classification terms, and `baseline:` block.
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
artifact: <path-to-richer-report-if-any>
taste_test: inline-pass | dispatched-pass | revised | deferred-to-orchestrator
durable_flags: none | <one line per flag: what durable knowledge changed -> target wiki page>
baseline: none | <block — shape in references/quality-gates.md § Baseline block shape>
<one-line orientation: what cook changed>
```

The [handback contract](../cheese/references/handback-contract.md) defines the canonical `status:` grammar.
Only `next:` and the additional keyed lines are specific to a phase.

When you emit this handoff for the typed fan result, use the canonical boundary writer.
Carry the result schema explicitly:

```text
python3 skills/cook/scripts/cook.pyz write-handoff-artifact \
  --slug <slug> --status <status> --phase cook --next age \
  --artifact <artifact-path> --orientation "<one-line orientation>" \
  --payload-schema https://schemas.easy-cheese.dev/curd-result
```

For a deliberate replan handoff, use `--next mold` with the `https://schemas.easy-cheese.dev/planner-request` payload.
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
Use `baseline:` to summarize Cook's optional comparison.
Include baseline-identical debt and new or changed failures from current broad gates.
Use the baseline block in [`references/quality-gates.md`](references/quality-gates.md).

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
Cook does not invoke `/plate`.
Terminal Cure owns publication.

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
A spawned phase agent does not chain forward by itself.
The orchestrator controls the chain.
The reference also contains the final report template.

## Rules

- Keep changes scoped to the accepted contract.
- Prefer existing dependencies and patterns.
- Do not invent architecture already rejected by the spec.
- Stop and ask when implementation reveals a design decision that the spec does not answer.
- Stop if the spec or fast-path request uses a false premise.
- Show the false premise before you write code.
- Do not use an incorrect approach to satisfy the request literally.
- Apply the shared voice kernel in `../age/references/voice.md`.
- Start the report with the answer.
- Name loaded assumptions in the contract.
- Mark residual risk as `certain | speculating | don't know`.
- **Verification before `status: ok`:** identify the gate command.
- Run the gate command during the current turn.
- Read the complete output before you make the claim.
- Do not use `should`, `probably`, or `I think`.
- State what the gate output shows.

## Discipline

Iron Law, Red Flags, and the TDD Rationalization table live in
[`references/cook-discipline.md`](references/cook-discipline.md).

## Agent resolution

Resolve through
[`agent-resolution.md`](../cheese/references/agent-resolution.md). Implementation
uses a coder, taste-test uses a reviewer, and harvest and plate stay parent-owned.

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Decompose the spec | planner, general | write (manifest only), fresh-context | powerful | high | compatible planner, then general |

The handoff carries the `agent_resolution` block.
Publish a terminal Age only when it contains `next: done`.
Stop when it contains `next: cure` or does not contain `next`.

Generated bundle command inventory: [`references/commands.md`](references/commands.md).
