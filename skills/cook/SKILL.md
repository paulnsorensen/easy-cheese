---
name: cook
description: Implement an approved spec or focused unambiguous task through stale-safe source edits. Use when the user wants code written — "implement this", "cook this spec", "/cook .cheese/specs/<slug>.md", or "fix this bug" when the fix is clear; also when the user just says "go" or "ship it" with a spec or clear acceptance criteria in scope. Runs standalone on an unambiguous task — a spec helps but is not required. Do NOT use for fuzzy planning (`/mold`), no-write discussion (`/culture`), or review-only work (`/age`).
license: MIT
metadata: {dispatches-agents: true}
---

# /cook
## Contract

`cook(spec_ref, receipt? = null, correction = false) -> handoff(next = press | age)`.
`GateReceipt` is the sole outer-oracle authority: hold a canonical receipt
before any production mutation, bound to the same `spec_ref`, canonical
`work_id`, and sanitized `project_key`. An absent or invalid receipt
synchronously invokes `/cut` exactly once; a user or Pasteurize reproduction
retains `producer: cut` and `origin: adopted`.
Every newly issued receipt also carries the exact pre-oracle
`phase_token_ref`/`phase_token_sha256`; validation treats that pair as part of
the receipt identity evidence. Cook never recreates or substitutes a token.

For an active RED receipt, run `red-gate validate <receipt> --state red` before
editing and keep the outer oracle immutable. The single-coder path and the
post-merge fan path validate the complete receipt GREEN, including every
transitive guard, before the global Press. Fan curd workers replay RED only:
they never run Press or claim whole-receipt GREEN while sibling cases remain
RED. `correction = true` is scoped to the active Press RED receipt and may not
weaken any transitive guard.
Closed N/A receipts retain identity and structural validation, skip only outer
RED replay, and run requested docs/refactor/test/appearance work through its
non-behavior path; N/A never means no requested work.

## Packaged validator

Resolve `red-gate ...` through
[`../cut/references/gate-workflow.md`](../cut/references/gate-workflow.md)
§ Packaged command resolution: installed sibling `cut.pyz` first, then the
source-checkout bundle. A bare executable is not on PATH.

## GateReceipt preflight

1. Resolve the approved spec without mutating production.
2. When the receipt is absent or fails canonical loading, synchronously invoke
   `/cut` and consume its returned receipt exactly once; Cut never dispatches
   Cook back into this call.
3. For a valid RED receipt, run
   `red-gate validate <receipt> --state red`; no production path may run before
   it succeeds. Consume the receipt's frozen pre-Cut broad-gate
   `baseline_checks` exactly; do not overwrite them or capture a replacement.
   Baseline argv must exclude protected RED-oracle paths or remain green with
   the oracle present, because validation replays them after oracle creation.
4. For closed N/A, retain identity and structural validation, skip only outer
   RED replay, then route the requested work through its non-behavior
   implementation and verification path. Do not treat N/A as no work.

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

`/cook` bypasses `/mold` only when inputs/outputs and scope are clear and verification is obvious: a named bug/callsite in one or two files with a failing test or runnable expected-output check. Derive a slug, restate the **Contract**, then run GateReceipt preflight. Any failed ambiguity check routes to `/mold`.

## Flow

1. **Contract** — confirm behaviour, non-goals, scope, gates, and applicability.
2. **GateReceipt preflight** — obtain a canonical receipt; invoke Cut once when
   missing or invalid.
3. **Replay RED** — run `red-gate validate <receipt> --state red`; closed N/A
   skips only outer RED replay after identity/structural validation, then
   follows the non-behavior implementation/verification path.
4. **Implement** — behavior changes use inner RED → GREEN; closed N/A work
   uses its requested non-behavior implementation path. Only the applicable
   path may mutate its requested surface. Never mutate receipt-protected files
   or the outer oracle.
5. **Validate GREEN** — the single-coder and post-merge fan paths run
   `red-gate validate <receipt> --state green` for the complete receipt and
   every transitive guard; fan curd workers do not issue this whole-receipt
   validation. For closed N/A, verify the requested non-behavior path.
6. **Taste-test** — fresh-context review for multi-file/public-surface diffs;
   otherwise inline. Two-round cap; details: `references/tdd-loop.md`.
7. **Hand off** — write the package report and slug. An active RED receipt
   proceeds `/press → /age → /cure`; a closed N/A receipt has no adversarial
   contract for Press and proceeds directly `/age → /cure`.

## Fan pathway

`/cook` routes a spec through one of three shapes, gated on whether a typed
planner result is already available. Every shape runs GateReceipt preflight.
Cut runs before Seed when needed; protected-oracle propagation gives Seed and
every curd the same protected oracle before RED replay. The complete topology
lives in [`references/fan-pathway.md`](references/fan-pathway.md).

**Fast path.** When the curd-count hint is `1` with low or medium blast radius,
use the ordinary single-coder path.

**Curded.** Load the typed `PlannerResult` or `CurdPlan`, run
`validate_curd_plan`, and treat that plan as semantic authority. Active RED
curds run `cook(CurdPlan) → reviewer(age) → cure(CurdPlan, binding) →
reviewer(final age)` without Press or whole-receipt GREEN claims. After wiring,
validate the complete receipt GREEN, then run one global
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
topology, oracle transfer, deterministic phase execution, recovery, resume,
Milknado integration, worktree teardown, and resolution provenance. Propagate
`--auto` through dispatched phases when active.

## Baseline capture

Cut owns the outer baseline: it runs broad gates on the pre-oracle tree and
freezes `baseline_checks` in the receipt before the protected RED oracle.
Cook validates and consumes that evidence; it never recaptures or replaces it.

Fan mode records its separate quality-debt comparison before any curd cooks;
bare mode records it on the pre-change tree. Neither replaces Cut's receipt.
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
status: ok | halt: <one-line reason>
next: mold | cut | cook | press | age | done
artifact: <path-to-richer-report-if-any>
taste_test: inline-pass | dispatched-pass | revised | deferred-to-orchestrator
durable_flags: none | <one line per flag: what durable knowledge changed -> target wiki page>
baseline: none | <block — shape in references/quality-gates.md § Baseline block shape>
<one-line orientation: what cook changed>
```

When this handoff is emitted for the typed fan result, use the canonical
boundary writer and carry the result schema explicitly:

```text
python3 skills/cook/scripts/cook.pyz write_handoff_artifact \
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

`next:` is the next runnable phase: `press` after RED-required work, `age` after
closed N/A, `cook` after a blocker, `mold` after a spec failure, or `done` only
at true completion. Never send contractless N/A to Press. Omit `taste_test:`
when its cost gate did not apply.

`durable_flags:` defaults to `none`; record only durable
architecture/protocol/convention/rationale changes and their target wiki page.
`baseline:` summarizes Cook's optional comparison when current broad gates
contain baseline-identical debt or new/changed failures. It never replaces the
receipt's canonical pre-Cut `baseline_checks`; use
[`references/quality-gates.md`](references/quality-gates.md) § Baseline block
shape.

## Handoff

**Pipeline:** culture → mold → **[cut]** → cook → press → age → cure → plate

After the package-ready report and handoff slug are on disk, ask via the shared handoff gate in [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md) (its **Standard forward-step menu**). For an active RED receipt, lead each option with the verb and use:

- **Harden tests before review** *(recommended)* — `/press <slug>`.
- **Plate it** — `/press <slug> --auto --open-pr`: run the remaining review chain, then `/plate` resolves topology and publishes.

For closed N/A, Press is structurally inapplicable. Set `next: age` and replace those options with **Review the change** *(recommended)* — `/age <slug>` and **Plate it** — `/age <slug> --auto --open-pr`.

Both menus retain **Checkpoint & stop** — `/wheypoint` and **Stop** — dispatch none. Never dispatch before selection; run the selected command immediately. When invoked with `--auto`, skip this gate and take the receipt-specific route directly.

## Auto mode

`--auto` never bypasses GateReceipt preflight or applicable validation. Active
RED runs `/press --auto → /age --auto → /cure --auto --stake medium+`; closed
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
