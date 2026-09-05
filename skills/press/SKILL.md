---
name: press
description: Run the tests-only adversarial gate after `/cook`. Route bounded corrective Cook continuations. Use this skill when the user says "press the changes", "harden this", "press before /age", or "/press". Do not edit production code. Do not dispatch a global Cook repair from Press.
license: MIT
---

# /press

Press is the tests-only adversarial gate after `/cook`. Its skill contract is:

```text
press(spec_ref)
  -> Continue("press-corrective-cook")
   | Dispatch("/age")
   | Stop(reason)
```

Press never owns first coverage. Press never edits production code. Cook owns the implementation. Press attacks the approved contract and preserves failure evidence for a bounded Cook repair.

## Inputs

Press accepts this invocation:

```text
/press <slug> [--auto] [--hard] [--open-pr]
```

`<slug>` names the pipeline slug. Press requires it. Press reads `.cheese/cook/<slug>.md` for the Cook handoff.

`--auto` selects the autonomous chain. See `## Auto mode`.

`--hard` requests the optional final gate. Press forwards this flag to Age.

`--open-pr` is publication permission. Only the user supplies it. Press forwards this flag to Age. Press never adds it.

Press preserves the Cook `durable_flags:` value without change. Press ignores the Cook `taste_test:` value.

## Packaged commands

Run this command for boundary routing:

```sh
python3 skills/press/scripts/press.pyz press-route \
  .cheese/press/<slug>.attempt-N.route.json
```

The request contains only `outcome` and `repair_cycles`:

```json
{
  "outcome": "green",
  "repair_cycles": 0
}
```

Set `outcome` to `green`, `in_contract_red`, `invalid_evidence`, or `production_changed`.

Set `repair_cycles` to the number of completed corrective Cook continuations. Use 0 for the first attempt.

Use the command JSON action as the authority. Stop if the bundle does not exist.

Use separate append-only artifact names for each Press attempt. Use the same `<slug>` for all three attempts. Never reuse an attempt number.

Use these paths:

- Attack candidate: `.cheese/press/candidates/<slug>.attempt-N.json`
- Route request: `.cheese/press/<slug>.attempt-N.route.json`
- Telemetry request: `.cheese/press/<slug>.attempt-N.telemetry-request.json`
- Telemetry record: `.cheese/press/<slug>.attempt-N.telemetry.json`

A third in-contract RED returns `Stop("third-red")`. Do not create attempt-4 paths. Do not overwrite an earlier path.

## Execution telemetry

Run this command after routing:

```sh
python3 skills/press/scripts/press.pyz press-telemetry \
  .cheese/press/<slug>.attempt-N.telemetry-request.json
```

Save the output at `.cheese/press/<slug>.attempt-N.telemetry.json`. The record contains these values:

- Attempt outcome
- Retry count
- Tool errors for each phase
- Purpose for each delegated agent
- Class for each changed file

Telemetry never controls the route. See [`references/telemetry.md`](references/telemetry.md).

## Adversarial loop

1. **Attack** — Add or run only tests, fixtures, and test-only harness support. Use the approved seam and witness. Keep the attack identity and test digest stable.
2. **Classify** — Use `in_contract_red` for an in-contract failure. Use `green` for a clean pass. Use `production_changed` when the attempt changed production paths. Use `invalid_evidence` when you cannot verify the evidence.
3. **Repair** — Route `in_contract_red` with the completed corrective count. Counts 0 and 1 return `Continue("press-corrective-cook")`. Count 2 returns `Stop("third-red")`.
4. **Replay** — Replay the same attack after the corrective Cook returns. Use the same attack and test digest. Then classify the result again.
5. **Terminate** — Return `Dispatch("/age")` only after GREEN.

Invalid evidence returns a stop. A production tree change also returns a stop. These outcomes never return a continuation.

Press has no global `dispatch: /cook` action. Press owns the corrective Cook `Continue` action.

## Baseline-aware gates

Press preserves baseline-aware readiness for project gates. The Cook `baseline:` line names one artifact. That artifact holds the settled state.

Read the artifact through the `baseline:` path. Do not re-flag a failure when its test and signature match the artifact. New or changed failures block the route.

See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md). Also see [`references/gap-analysis.md`](references/gap-analysis.md).

## Flow

1. **Read** — Load the approved spec, Cook handoff, and baseline block. Use canonical terms from `.cheese/glossary/<slug>.md` when that file exists.
2. **Attack** — Add or run only adversarial tests. Do not add first-coverage tests. Do not change production paths.
3. **Classify** — Select `green`, `in_contract_red`, `invalid_evidence`, or `production_changed` from the adversarial run.
4. **Continue or stop** — Run `press.pyz press-route` with `outcome` and `repair_cycles`. Only `Continue`, `Dispatch`, and `Stop` action shapes are public.
5. **Report** — Write `.cheese/press/<slug>.md` at a terminal result. Include the attempts, evidence, and review follow-ups.
6. **Hand off** — Send only a GREEN `Dispatch("/age")` to the global Age route.

Use [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md) for source changes.

Use [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md) for portability.
The reference states that slash commands are host renderings, not the control model.

Press reports one readiness value. Map `ready for /age` to `status: ok` and `next: age`.

Map `follow-up recommended` to `status: ok-with-concerns: <concern>` and `next: age`. Use this status for a GREEN pass that also records a review follow-up. Age owns each recorded concern.

Map `blocked` to `status: gated: <decision>` and `next: done`. Stop after that status.

## Auto mode

`--auto` runs the same adversarial loop. It also selects the next phase without a user prompt.

Dispatch `/age <slug> --auto` after `ready for /age` or `follow-up recommended`. Add `--hard` when the user supplied it. Add `--open-pr` when the user supplied it.

Stop after `blocked`. Do not dispatch Age.

Honor the no-chain directive when the caller supplies it. Write the Press handoff and stop. Do not start another phase. Cook's fan pathway owns this directive. The retired `/ultracook` orchestrator previously owned it. Test for the directive itself. Do not test for the source name. See [`../cook/references/auto-mode.md`](../cook/references/auto-mode.md).

## Output

Write `.cheese/press/<slug>.md` only at a terminal Press result. A corrective `Continue` stays inside the Press phase. It writes no durable handoff.

Write the file with `write-handoff-artifact`. Use the canonical preamble:

```markdown
status: <canonical status field>
next: age | done
artifact: .cheese/cook/<slug>.md
durable_flags: <preserved Cook value>
baseline: none | <baseline artifact path>
<one-line orientation>
```

The [handback contract](../cheese/references/handback-contract.md) defines the `status:` grammar. The preamble accepts no other keys. Put every Press value in the report body.

`artifact:` names the consumed Cook report. Do not put attack evidence on this line.

`baseline:` names the one artifact that Cook recorded. See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md).

Write these body sections under the preamble:

- `## Attempts` — one row for each attempt. Give the attempt number, outcome, router action, candidate path, route path, and telemetry record path.
- `## Evidence` — the stable attack identity and the test digest.
- `## Review follow-ups` — each out-of-contract concern. Write `none` when the run records no concern. Age reads this section.

Map the router action to the terminal preamble:

| router action | status | next |
| --- | --- | --- |
| `Dispatch("/age")` after GREEN | `ok` | `age` |
| `Dispatch("/age")` after GREEN with a recorded concern | `ok-with-concerns: <concern>` | `age` |
| `Continue("press-corrective-cook")` on repair cycle 0 or 1 | no handoff | no handoff |
| `Stop("third-red")` | `ok` | `done` |
| invalid evidence or production change | `halt: <reason>` | `done` |

`next: done` is terminal. It never starts another phase.

A valid third-RED stop is ready for terminal reporting. It does not dispatch Age. It can offer a later Cook handoff that the user selects.

Reserve `next: age` for a GREEN `Dispatch("/age")`. The corrective `Continue` belongs to Press. It is not a global phase handoff. Do not write `next: press`.

## Handoff

**Pipeline:** culture → mold → cook → **[press]** → age → cure → plate

After a GREEN Press report, use the shared [handoff gate](../cheese/references/handoff-gate.md). Start the review with `/age <slug>`.

The Press owner controls a corrective Cook continuation. Do not offer that continuation as a second global route.

Forward `--hard`, `--auto`, and `--open-pr` to `/age` when the caller supplied them. Never add `--open-pr`.

## Rules

- Do not edit production code, production fixtures, or production adapters.
- Do not dispatch a global Cook repair from Press.
- Do not use more than two corrective continuations.
- Do not change the attack between retries.
- Do not treat out-of-contract behavior as an implementation request. Record it under `## Review follow-ups`. Report the run as `ok-with-concerns` on a GREEN pass.
- Preserve baseline-aware readiness unless these route rules replace it.

## Discipline

Press uses evidence first. An unverified failure is not a RED.

Name the outcome before each route decision. Name the attack digest and completed `repair_cycles` count. Stop if one value is missing. Do not guess.

Generated bundle command inventory: [`references/commands.md`](references/commands.md).
