---
name: cook
description: >-
  Implement an approved spec or focused task through stale-safe source edits.
  Use this skill when the user says "implement this", "cook this spec", or "fix this bug".
  Use it for `/cook .cheese/specs/<slug>.md`.
  Also use it when the user says "go" with clear acceptance criteria.
  Run it alone for an unambiguous task.
  Use `--prototype` when the user says "prototype this", "go prototype it", or "spike this out" and wants to refine the result round by round.
  A spec helps but is not required.
  Do not use it for fuzzy planning (`/mold`).
  Do not use it for no-write discussion (`/culture`) or review-only work (`/age`).
license: MIT
metadata: {dispatches-agents: true}
---

# /cook

## Contract

`cook(spec_ref, correction = false) -> handoff(next = age | mold | done)`.

Cook returns `next: mold` for a specification failure.
A fan run also returns `next: mold` for a stalled remediation scope, a curd that does not pass, or partial coverage.

Cook does not require a failing test first and does not load a gate receipt.
For behavior work, Cook owns first acceptance coverage before Press; see `references/tdd-loop.md` § Inner TDD.
This is a reported obligation, not a gate.
For documentation, refactor, test, or appearance work, change that surface and verify it directly.
Use `correction = true` only for an active Press finding or `coverage_gap`; see `references/press-loop.md`.
Do not weaken an existing test.

## Phase entry

Run `python3 skills/cook/scripts/cook.pyz wheypoint-resolve --ref <slug>`.
`authoritative` uses the record; its `working_context` is the first batched `tilth_read`.
`not-found` proceeds cold; `legacy` shows its source and slug, then proceeds.
`gated`, `ambiguous`, and `error` stop and show the payload.
Show advisory `stale-commit` and `grounded-path-missing` findings.
Keep its `record.revision_id` as `<base>` ([§ Base revision](../cheese/references/handback-contract.md#base-revision)).

## Inputs

Accept a pasted spec or issue, focused acceptance criteria, or an unambiguous task.
Read explicit spec paths verbatim.
Resolve a bare slug to `path` from `python3 skills/cook/scripts/cook.pyz artifact-path specs <slug>`.
A Mold spec path or finalized direct inputs enter through § Mold-to-Cook ingress.
Flags:

- `--auto` chains `/age → /cure` after the in-Cook Press loop.
- `--prototype` runs a plan → spike → check loop, then stabilizes; read [`references/prototype-mode.md`](references/prototype-mode.md).
- `--hard` propagates through `/plate`.
- `--open-pr` lets terminal `/plate` publish. Auto mode never adds this flag.
- `--resume <slug>` resumes a typed fan handoff and its referenced artifacts.
- `--result <path>` runs a ready Mold result.
- `--spec <spec-path>` names the selected Mold spec. A plan whose `dependencies` cross `landing.layers` is refused before coder dispatch.

Optional context payload:

- `handoff_context.wiki_hits` carries `{page, line, why}` entries from the repository wiki corpus.
  The key is optional, and its default is absent.
  Reject an entry that omits `page`, `line`, or `why`.
  Show every accepted hit in the **Contract** step so the user can challenge a stale decision; prefer these decisions over an invented approach.
  [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md) defines the payload.

Read `references/auto-mode.md`, `references/fan-pathway.md`, and `../cheese/references/formatting.md` for these policies.

### Standalone fast-path

`/cook` bypasses `/mold` only when the inputs, outputs, scope, and verification are clear.
The task must name a bug or call site in one or two files and have a failing test or an expected-output check.
No leverage trigger may fire; see `../cheese/references/routing-policy.md` § Leverage triggers.
Derive a slug, then restate the **Contract**.
Route the task to `/mold` if an ambiguity check fails.

## Flow

1. **Contract** — Confirm behavior, non-goals, scope, and gates.
   Print the shape-check block from `../mold/references/shape-check.md` inside the Contract, or the line `shape check skipped: single-module change` per `shape-check.md` § When to skip. No block, no code.
   If `.cheese/glossary/<slug>.md` exists, use its canonical terms.
2. **Implement** — Write the test first where it fits; no gate requires it.
   For non-behavior work, change only the applicable surface.
3. **Validate** — Run the relevant quality gates again.
   Read the complete gate output; for non-behavior work, verify the requested path.
4. **Taste-test** — Use a fresh-context review for multi-file or public-surface diffs.
   Otherwise use an inline review, limited to two rounds.
   Read `references/tdd-loop.md` for details.
5. **Press loop** — For behavior work, Cook dispatches a fresh-context Press agent; no menu.
   Read [`references/press-loop.md`](references/press-loop.md).
   Non-behavior work skips this step.
6. **Hand off** — Write the package report and slug, then route to `/age → /cure`.

## Fan pathway

`/cook` selects one of three shapes from the typed planner result.
Read [`references/fan-pathway.md`](references/fan-pathway.md) for topology and lifecycle.

**Fast path.** Use the single-coder path for one low- or medium-blast-radius curd.

**Curded.** Require a bound `spec_ref`, `planner_result_ref`, `plan_ref`, and exact `MoldCookCoverage` from a ready Mold finalization. The host validates them before `execute_bound_plan` dispatches any writer.
Run `cook(CurdPlan) → reviewer(age)` with confirmed diagnosis and `CureDiagnosisBinding` through the progress-aware fan state machine until clean, stalled, or blocked.
Each curd's Cook loop runs its own Press loop.
The barrier runs Cook's integrated acceptance check on the merged tip.
No global post-merge Press runs.
Incomplete fan work never emits `next: press`; stalls route to Mold remediation planning.

**Un-curded.** Keep small work in the single-coder path.
For big work, ask "12 ACs -> 5 curds, 2 waves, up to 25 agent dispatches. Go?" unless `--auto`.
Keep waves at a maximum of four.

Use `python3 skills/cook/scripts/cook.pyz worktree teardown` for cleanup.
Propagate `--auto` through dispatched phases.

## Baseline capture

Fan mode records its quality-debt comparison before any curd cooks; bare mode records it on the pre-change tree.
[`references/quality-gates.md`](references/quality-gates.md) defines exact capture, classification, intentional-RED exclusion, and baseline-artifact rules.

For source changes, follow [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md) and [`harness-portability.md`](../cheese/references/harness-portability.md).
`slash commands are host renderings, not the control model`; invoke the equivalent installed capability.

## Quality gates

Run only existing project commands.
Run the most relevant tests for the changed area.
Also run lint, type, and build commands when the project defines them.
Do not remove, skip, or weaken unrelated tests to make the change pass.

Use the baseline for gate failures.
[`references/quality-gates.md`](references/quality-gates.md) defines the policy, the classification terms, and the baseline artifact.

[`references/writer-views.md`](references/writer-views.md) generates schemas for writer-view payloads inline.
The `normalize` and `validate` CLIs apply these schemas before agent-authored JSON reaches host-owned identifiers.

## Output

Use the house style in [`../cheese/references/formatting.md`](../cheese/references/formatting.md).
Use [`references/package-report.md`](references/package-report.md) to report files, reasons, checks, risks, and the next skill.

## Handoff slug

Write a minimum-shape handoff slug at the top of `.cheese/cook/<slug>.md`.
Use the same file for the report; do not create a second file.
Use this schema:

```markdown
status: <canonical status field>
next: mold | age | done
artifact: <path to the upstream artifact this run consumed, or empty>
taste_test: inline-pass | dispatched-pass | revised | deferred-to-orchestrator
durable_flags: none | <one line per flag: what durable knowledge changed -> target wiki page>
baseline: none | <path to the baseline artifact — shape in references/quality-gates.md § Baseline block shape>
<one-line orientation: what cook changed>
```

The handback contract defines the canonical `status:` grammar, including `ok` and `halt`.
Only `next:` and the additional keyed lines are specific to a phase.

`artifact:` names the upstream artifact that this run consumed.
For a Mold route, use the approved spec path.
Leave `artifact:` empty when this run consumed no upstream artifact.
Do not point `artifact:` at this Cook report.

Use the canonical boundary writer when you emit this handoff for the typed fan result.
Carry the result schema explicitly:

```text
python3 skills/cook/scripts/cook.pyz write-handoff-artifact \
  --slug <slug> --status <status> --phase cook --next age [--base <base>] \
  --artifact <artifact-path> --orientation "<one-line orientation>" \
  --payload-schema https://schemas.easy-cheese.dev/curd-result \
  --grounded <path[#start-end]> \
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
Use `age` after the Press loop returns `green`, and after non-behavior work.
Never publish `next: press` or `next: cook`; `needs-context` is a parent-owned same-phase retry.
Use `mold` after a spec failure.
Use `done` only at true completion.
Omit `taste_test:` when its cost gate does not apply.

Set `durable_flags:` to `none` by default.
Record only durable changes to architecture, protocols, conventions, or rationale.
Record the target wiki page for each change.
Set `baseline:` to the path of Cook's optional comparison artifact.
That artifact holds baseline-identical debt and new or changed failures from the current broad gates.
Use the shape in [`references/quality-gates.md`](references/quality-gates.md).
The preamble accepts one physical line for each key, so never inline the mapping.

## Handoff

**Pipeline:** culture → mold → cook (⇄ press) → age → cure → plate

After you write the report and slug, use the shared handoff gate.
Read its **Standard forward-step menu** in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md).
The menu never offers Press.
Behavior work reaches it only after the Press loop returns `green`.
Start each option with the verb.
Use these options for behavior and non-behavior work:

- **Review the change** *(recommended)* — `/age <slug>`.
- **Plate it** — `/age <slug> --auto --open-pr`: run the remaining review chain, then `/plate` resolves topology and publishes.
- **Checkpoint & stop** — `/wheypoint`.
- **Stop** — dispatch none.

Do not dispatch before selection.
Run the selected command immediately.
When the user invokes `--auto`, skip this gate.
Take the route to `/age` directly.

## Auto mode

Read [`references/auto-mode.md`](references/auto-mode.md) before auto mode.
It defines validation, phase chains, early stops, Cure limits, publication ownership, fan isolation, and failure handling.
Show each stopping report and reason; never downgrade the result.
In the linear chain, Cook does not invoke `/plate`.
In the fan pathway, the Cook orchestrator owns its own terminal `/plate` dispatch.
Fan progress state, not the legacy phase tables, decides each next action.

## No-chain isolation directive

A spawned phase agent does not chain forward by itself; the orchestrator controls the chain.

A terminal Age is publishable only with `next: done`.
`next: cure` or a missing `next` halts the chain.

## Rules

- Keep changes scoped to the accepted contract.
- Prefer existing dependencies and patterns.
- Build for the reviewer on the first pass: `references/tdd-loop.md` § Reviewable by construction.
- Keep import direction and crust integrity per [`../cheese/references/sliced-bread.md`](../cheese/references/sliced-bread.md).
- Stop before a new crust export, a cross-slice import of an internal, or a schema or contract change the spec does not name. Ask the user.
- Do not invent architecture that the spec already rejected.
- Stop and ask the user when implementation reveals a design decision that the spec does not answer.
- Stop and show the false premise before you write code if the spec or fast-path request uses one.
- Do not use an incorrect approach to satisfy the request literally.
- Apply the shared voice kernel in `../age/references/voice.md`; start the report with the answer and name loaded assumptions in the contract.
- Mark residual risk as `certain | speculating | don't know`.
- **Verification before `status: ok`:** Identify the gate command, run it during the current turn, and read the complete output before you make the claim.
- Do not use `should`, `probably`, or `I think`.
- State what the gate output shows.

## Agent resolution

Resolve through [`agent-resolution.md`](../cheese/references/agent-resolution.md).
Implementation uses a coder.
Taste-test uses a reviewer.
Harvest and plate stay parent-owned.

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Decompose the spec | planner, general | write (manifest only), fresh-context | powerful | high | compatible planner, then general |
| Press loop | coder | write (tests only), fresh-context | default | medium | general |

The handoff carries the `agent_resolution` block.
Publish a terminal Age only when it contains `next: done`.
Stop when it contains `next: cure` or does not contain `next`.

Generated bundle command inventory: [`references/commands.md`](references/commands.md).

## Mold-to-Cook ingress

A saved Mold spec is not execution authority. Start Cook only when the user requests the selected scope and route.
A standalone task, including `--spec` alone, may skip finalization.
Spec-hold refusal: refuse a `--spec` run whose frontmatter has `execution_holds` or a `do-not-implement` or `do-not-proceed` `request_directive`.
Refuse a non-`ready` `--result` file; a ready one passes `cook.pyz validate-result` before `execute_bound_plan`.
Follow [`references/fan-pathway.md`](references/fan-pathway.md) § Direct Mold-to-Cook ingress.
Run the fresh-agent regression scenarios in [`references/evals.md`](references/evals.md) when this boundary changes.
