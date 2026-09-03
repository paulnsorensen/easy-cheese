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

Press preserves baseline-aware readiness for project gates. A Cook `baseline:` block contains the settled state.

Do not report a failure again when its test and signature match the baseline. New or changed failures block the route.

See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md). Also see [`references/gap-analysis.md`](references/gap-analysis.md).

## Flow

1. **Read** — Load the approved spec, Cook handoff, and baseline block. Use canonical terms from `.cheese/glossary/<slug>.md` when that file exists.
2. **Attack** — Add or run only adversarial tests. Do not add first-coverage tests. Do not change production paths.
3. **Classify** — Select `green`, `in_contract_red`, `invalid_evidence`, or `production_changed` from the adversarial run.
4. **Continue or stop** — Run `press.pyz press-route` with `outcome` and `repair_cycles`. Only `Continue`, `Dispatch`, and `Stop` action shapes are public.
5. **Report** — Write `.cheese/press/<slug>.md`. Include the evidence, action, and telemetry record path.
6. **Hand off** — Send only a GREEN `Dispatch("/age")` to the global Age route.

Use [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md) for source changes.

Use [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md) for portability. Slash commands are host representations, not the control model.

Map `ready for /age` to `status: ok` and `next: age`. Map `follow-up recommended` to `status: ok-with-concerns: <concern>`. Continue after that status.

Map `blocked` to `status: gated: <decision>`. Stop after that status.

When `/ultracook` sets its no-chain directive, write the Press handoff and stop. Do not continue to another phase.

## Output

Write `.cheese/press/<slug>.md` with at least this content:

```markdown
status: <canonical status field>
next: age | press | done
artifact: <evidence-path>
baseline: none | <Cook baseline block>
action: continue | dispatch | stop
telemetry: <telemetry-record-path>
<one-line orientation>
```

The [handback contract](../cheese/references/handback-contract.md) defines the `status:` grammar. Only `next:` and the additional keyed lines are specific to Press.

Map the router action without a new runnable phase:

| router action | status | next | action |
| --- | --- | --- | --- |
| `Dispatch("/age")` after GREEN | `ok` | `age` | `dispatch` |
| `Continue("press-corrective-cook")` on repair cycle 0 or 1 | `ok` | `press` | `continue` |
| `Stop("third-red")` | `ok` | `done` | `stop` |
| invalid evidence or production change | `halt: <reason>` | `done` | `stop` |

`next: done` is terminal. It never starts another phase.

A valid third-RED stop can offer a later Cook handoff that the user selects. It does not set Cook, Press, or Age as the next phase.

Invalid evidence and production changes halt. Reserve `next: age` for GREEN `Dispatch("/age")`. A corrective `Continue` belongs to Press. It is not a global phase handoff.

## Handoff

**Pipeline:** culture → mold → cook → **[press]** → age → cure → plate

After a GREEN Press report, use the shared [handoff gate](../cheese/references/handoff-gate.md). Start the review with `/age <slug>`.

The Press owner controls a corrective Cook continuation. Do not offer that continuation as a second global route.

Pass `--hard` to `/age` and later phases.

## Rules

- Do not edit production code, production fixtures, or production adapters.
- Do not dispatch a global Cook repair from Press.
- Do not use more than two corrective continuations.
- Do not change the attack between retries.
- Do not treat out-of-contract behavior as an implementation request. Record it as a review follow-up.
- Preserve baseline-aware readiness unless these route rules replace it.

## Discipline

Press uses evidence first. Fear is the curd-killer. An unverified failure is not a RED.

Name the outcome before each route decision. Name the attack digest and completed `repair_cycles` count. Stop if one value is missing. Do not guess.

Generated bundle command inventory: [`references/commands.md`](references/commands.md).
