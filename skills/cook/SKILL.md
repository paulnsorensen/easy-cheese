---
name: cook
description: Implement an approved spec or focused unambiguous task through stale-safe source edits. Use when the user wants code written — "implement this", "cook this spec", "/cook .cheese/specs/<slug>.md", or "fix this bug" when the fix is clear; also when the user just says "go" or "ship it" with a spec or clear acceptance criteria in scope. Runs standalone on an unambiguous task — a spec helps but is not required. Do NOT use for fuzzy planning (`/mold`), no-write discussion (`/culture`), or review-only work (`/age`).
license: MIT
metadata: {dispatches-agents: true}
---

# /cook
## Contract

`cook(spec_ref, correction = false) -> handoff(next = press | age)`.
Behavior work (a `red-required` gate disposition) runs the inner RED → GREEN
TDD loop against the approved spec's test contracts before any production
mutation. Non-behavior work (a closed `not-applicable` disposition) routes the
requested docs/refactor/test/appearance change through its non-behavior
implementation and verification path; N/A never means no requested work.
`correction = true` is scoped to the active Press corrective loop and may not
weaken any existing test.

## Inputs

Accept a pasted spec/issue, focused acceptance criteria, or an unambiguous task.
Read explicit spec paths verbatim. Resolve a bare slug with
`SPEC=$(python3 skills/cook/scripts/cook.pyz artifact-path specs <slug>)`.

Flags: `--auto` chains `/press → /age → /cure`; `--hard` propagates through
`/plate`; `--open-pr` lets terminal `/plate` publish; `--resume <slug>` resumes
a typed fan handoff and its referenced artifacts. Their policies live in
`references/auto-mode.md`, `references/fan-pathway.md`, and
`../cheese/references/formatting.md`.

### Standalone fast-path

`/cook` bypasses `/mold` only when inputs/outputs and scope are clear and verification is obvious: a named bug/callsite in one or two files with a failing test or runnable expected-output check. Derive a slug, then restate the **Contract**. Any failed ambiguity check routes to `/mold`.

## Flow

1. **Contract** — confirm behaviour, non-goals, scope, gates, and applicability.
2. **Implement** — behavior changes use inner RED → GREEN; closed N/A work
   uses its requested non-behavior implementation path. Only the applicable
   path may mutate its requested surface.
3. **Validate** — run the relevant quality gates fresh and read the output.
   For closed N/A, verify the requested non-behavior path.
4. **Taste-test** — fresh-context review for multi-file/public-surface diffs;
   otherwise inline. Two-round cap; details: `references/tdd-loop.md`.
5. **Hand off** — write the package report and slug. Behavior work proceeds
   `/press → /age → /cure`; a closed N/A change has no adversarial contract
   for Press and proceeds directly `/age → /cure`.

## Fan pathway

`/cook` routes a spec through one of three shapes, gated on whether a typed
planner result is already available. The complete topology lives in
[`references/fan-pathway.md`](references/fan-pathway.md).

**Fast path.** When the curd-count hint is `1` with low or medium blast radius,
use the ordinary single-coder path.

**Curded.** Load the typed `PlannerResult` or `CurdPlan`, run
`validate_curd_plan`, and treat that plan as semantic authority. Behavior
curds run `cook(CurdPlan) → reviewer(age) → cure(CurdPlan, binding) →
reviewer(final age)` without Press. After wiring, run one global
`/press → /age → /cure` chain. Closed N/A bypasses Press.

Worktree cleanup uses `python3 skills/cook/scripts/cook.pyz worktree teardown`; the fan-pathway reference owns its arguments and lifecycle.

**Un-curded.** Small work stays single-coder. Big work asks
"12 ACs -> 5 curds, 2 waves, up to 25 agent dispatches. Go?" unless `--auto`.
Waves remain capped at four. Legacy decomposition is a lossless projection
only, never live workflow state.
Sizing and decomposition follow
[`decomposer.md`](../cheese/references/decomposer.md).

Before orchestrating, read
[`references/fan-pathway.md`](references/fan-pathway.md). It owns sizing,
topology, deterministic phase execution, recovery, resume,
Milknado integration, worktree teardown, and resolution provenance. Propagate
`--auto` through dispatched phases when active.

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

Run existing project commands only — the most relevant tests for the touched area, plus lint/type/build if defined. Never remove, skip, or weaken unrelated tests to make the change pass.

Gate failures are baseline-aware. Policy, the classification taxonomy, and the `baseline:` block shape are the shared reference [`references/quality-gates.md`](references/quality-gates.md); every downstream phase links there instead of restating it.

Writer-view payload schemas are generated inline in [`references/writer-views.md`](references/writer-views.md); `normalize`/`validate` CLIs structure agent-authored JSON against them before it reaches host-owned identifiers.

## Output

House style: [`../cheese/references/formatting.md`](../cheese/references/formatting.md). Report files, reasons, checks, risks, and next skill using the authoritative [`references/package-report.md`](references/package-report.md).

## Handoff slug

Write a minimum-shape handoff slug at the top of `.cheese/cook/<slug>.md` — same file as the report, no second file — so downstream phases (and cook's own fan pathway when orchestrating a wave) can resume or chain without re-reading it. Schema:

```markdown
status: <canonical status field>
next: mold | cook | press | age | done
artifact: <path-to-richer-report-if-any>
taste_test: inline-pass | dispatched-pass | revised | deferred-to-orchestrator
durable_flags: none | <one line per flag: what durable knowledge changed -> target wiki page>
baseline: none | <block — shape in references/quality-gates.md § Baseline block shape>
<one-line orientation: what cook changed>
```

`status:` grammar is canonical in [handback contract](../cheese/references/handback-contract.md); only `next:` and the extra keyed lines are phase-specific.

When this handoff is emitted for the typed fan result, use the canonical
boundary writer and carry the result schema explicitly:

```text
python3 skills/cook/scripts/cook.pyz write-handoff-artifact \
  --slug <slug> --status <status> --phase cook --next age \
  --artifact <artifact-path> --orientation "<one-line orientation>" \
  --payload-schema https://schemas.easy-cheese.dev/curd-result
```

For a deliberate replan handoff, use `--next mold` with the
`https://schemas.easy-cheese.dev/planner-request` payload instead. These
`phase`/`next` values route the legacy handoff file only; the live fan state is
still the validated `CurdPlan` and normalized `CurdResult`.

In a fan run, read each phase's handoff slug file from disk; never infer the
handoff from stdout.

`next:` is the next runnable phase: `press` after red-required behavior work,
`age` after closed N/A, `cook` after a blocker, `mold` after a spec failure, or
`done` only at true completion. Never send contractless N/A to Press. Omit
`taste_test:` when its cost gate did not apply.

`durable_flags:` defaults to `none`; record only durable
architecture/protocol/convention/rationale changes and their target wiki page.
`baseline:` summarizes Cook's optional comparison when current broad gates
contain baseline-identical debt or new/changed failures; use
[`references/quality-gates.md`](references/quality-gates.md) § Baseline block
shape.

## Handoff

**Pipeline:** culture → mold → cook → press → age → cure → plate

After the package-ready report and handoff slug are on disk, ask via the shared handoff gate in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md) (its **Standard forward-step menu**). For behavior work, lead each option with the verb and use:

- **Harden tests before review** *(recommended)* — `/press <slug>`.
- **Plate it** — `/press <slug> --auto --open-pr`: run the remaining review chain, then `/plate` resolves topology and publishes.

For closed N/A, Press is structurally inapplicable. Set `next: age` and replace those options with **Review the change** *(recommended)* — `/age <slug>` and **Plate it** — `/age <slug> --auto --open-pr`.

Both menus retain **Checkpoint & stop** — `/wheypoint` and **Stop** — dispatch none. Never dispatch before selection; run the selected command immediately. When invoked with `--auto`, skip this gate and take the disposition-specific route directly.

## Auto mode

`--auto` never bypasses applicable validation. Behavior work
runs `/press --auto → /age --auto → /cure --auto --stake medium+`; closed
N/A skips Press and runs `/age --auto → /cure --auto --stake medium+`. Both
routes cap Cure at two passes. Cook never invokes `/plate`; terminal Cure owns
publication.

Auto mode stops early when: a quality gate fails new or changed against baseline and the fix rounds exhaust, the no-progress check trips, or the fix is design-shaped; `/press` returns `blocked`; a cure pass cannot apply any finding; or two cure passes complete (success path). Every early stop surfaces the failing skill's report and states the cap reached or the blocker hit — never a silent downgrade.

Read [`references/auto-mode.md`](references/auto-mode.md) before running or dispatching auto mode — it owns the full per-step chain, cap-enforcement mechanics, the fan-pathway no-chain isolation directive (a spawned phase sub-agent never chains forward on its own; the orchestrator drives), cure's per-finding failure handling, and the final-report template.

## Rules

- Keep changes scoped to the accepted contract.
- Prefer existing dependencies and patterns.
- Do not invent architecture already rejected by the spec.
- Stop and ask when implementation reveals a design decision the spec did not answer.
- If the spec or fast-path request rests on a false premise, stop and surface it before writing code; do not work the wrong angle to honour the request literally.
- Apply the shared voice kernel (`../age/references/voice.md`): lead the report with the answer, name loaded assumptions in the contract, flag residual risk as `certain | speculating | don't know`.
- **Verification before `status: ok`:** identify the gate command, run it fresh this turn, read the full output, only then claim. Hedging words (`should`, `probably`, `I think`) are banned — state what the gate output showed.

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
A terminal Age is publishable only with `next: done`; `next: cure` or a missing `next` halts.

Generated bundle command inventory: [`references/commands.md`](references/commands.md).
