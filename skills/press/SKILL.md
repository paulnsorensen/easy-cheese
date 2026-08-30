---
name: press
description: Run the tests-only adversarial gate after `/cook`, routing bounded corrective Cook continuations. Use when the user says "press the changes", "harden this", "press before /age", or "/press". Do NOT edit production code or dispatch a global Cook repair from Press.
license: MIT
---

# /press

Press is the tests-only adversarial gate after `/cook`. Its skill-level
contract is:

```text
press(spec_ref)
  -> Continue("press-corrective-cook")
   | Dispatch("/age")
   | Stop(reason)
```

Press never owns first coverage and never edits production code. Cook owns the
implementation; Press only attacks the approved contract and preserves the
failing evidence for a fresh bounded Cook repair.

## Packaged commands

For boundary routing, run `python3 skills/press/scripts/press.pyz press-route
.cheese/press/<slug>.attempt-N.route.json`. The request has exactly `outcome`
and `repair_cycles`:

```json
{
  "outcome": "green",
  "repair_cycles": 0
}
```

`outcome` is one of `green`, `in_contract_red`, `invalid_evidence`, or
`production_changed`. `repair_cycles` counts the corrective Cook continuations
already completed for this slug (0 on the first attempt). The command's JSON
action is authoritative. Halt if the bundle does not exist.

Each Press attempt has its own append-only artifact names. Use the same
`<slug>` for all three attempts, but never reuse an attempt number: the attack
candidate lives at `.cheese/press/candidates/<slug>.attempt-N.json` and the
route request at `.cheese/press/<slug>.attempt-N.route.json`. A third
in-contract RED routes to terminal `Stop("third-red")`; do not create
attempt-4 names or overwrite any earlier path.

## Adversarial loop

1. **Attack** — add or run only tests, fixtures, and test-only harness support
   against the same approved seam and witness. Keep the attack identity and
   failing-test digest stable.
2. **Classify** — an in-contract failure is `in_contract_red`; a clean pass is
   `green`; an attack whose interval mutated production paths is
   `production_changed`; anything unverifiable is `invalid_evidence`.
3. **Repair** — route `in_contract_red` with the completed corrective count:
   `repair_cycles` 0 and 1 return `Continue("press-corrective-cook")`;
   `repair_cycles` 2 returns the terminal `Stop("third-red")`.
4. **Replay** — after the corrective Cook returns, replay the identical attack
   with the same attack/test digest before classifying again.
5. **Terminate** — GREEN returns the only global dispatch, `Dispatch("/age")`.

Invalid evidence and any production-tree mutation return a stop. They do not
return a continuation. Press has no global `dispatch: /cook` action; the
corrective Cook is a Press-owned `Continue` action only.

## Baseline-aware gates

Press preserves baseline-aware readiness behavior for project gates. A Cook `baseline:` block is settled state: failures with the same test and signature do not re-flag or re-halt; new or changed failures remain blocking. See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md) and [`references/gap-analysis.md`](references/gap-analysis.md).

## Flow

1. **Read** — load the approved spec, Cook handoff, and any baseline block. If
   `.cheese/glossary/<slug>.md` exists, use its canonical terms.
2. **Attack** — add or run adversarial tests only; do not add first-coverage
   tests or alter production paths.
3. **Classify** — name the outcome from the adversarial run: `green`,
   `in_contract_red`, `invalid_evidence`, or `production_changed`.
4. **Continue or stop** — invoke packaged `press.pyz press-route` with
   `outcome` and `repair_cycles`. Only its returned `Continue`, `Dispatch`,
   and `Stop` action shapes are public.
5. **Report** — write `.cheese/press/<slug>.md` with the evidence and action.
6. **Hand off** — only a GREEN `Dispatch("/age")` reaches the global Age route.

Compatibility contracts: source changes follow [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md). Portability follows [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md); slash commands are host renderings, not the control model. Readiness `ready for /age` maps to `status: ok` and `next: age`; `blocked` or `follow-up recommended` maps to `status: halt`. When invoked from `/ultracook` with its no-chain directive, write the Press handoff and stop; do not chain forward.

## Output

Write `.cheese/press/<slug>.md` with this minimum handoff shape:

```markdown
status: ok | halt: <one-line reason>
next: age | press | done
artifact: <evidence-path>
baseline: none | <Cook baseline block>
action: continue | dispatch | stop
<one-line orientation>
```

Project the router action without inventing a runnable phase:

| router action | status | next | action |
| --- | --- | --- | --- |
| `Dispatch("/age")` after GREEN | `ok` | `age` | `dispatch` |
| `Continue("press-corrective-cook")` on repair cycle 0 or 1 | `ok` | `press` | `continue` |
| `Stop("third-red")` | `ok` | `done` | `stop` |
| invalid evidence or production change | `halt: <reason>` | `done` | `stop` |

`next: done` is terminal and never auto-dispatches. A valid third-RED stop may
offer a later user-selected Cook handoff, but it does not encode Cook, Press,
or Age as its next phase. Invalid evidence and production changes halt.
`next: age` is reserved for GREEN `Dispatch("/age")`; a corrective `Continue`
is Press-owned and is not a global phase handoff.

## Handoff

**Pipeline:** culture → mold → cook → **[press]** → age → cure → plate

After a GREEN Press report, use the shared [handoff gate](../cheese/references/handoff-gate.md) to review with `/age <slug>`. A Press corrective Cook continuation is driven internally by
the Press owner and is not offered as a second global route. `--hard` remains
pass-through to `/age` and later phases.

## Rules

- Do not edit production code, production fixtures, or production adapters.
- Do not dispatch a global Cook repair from Press.
- Do not exceed two corrective continuations or change the attack between
  retries.
- Do not treat out-of-contract desired behavior as an implementation request;
  record it as a follow-up for review.
- Preserve existing baseline-aware hardening/readiness behavior where it is
  not superseded by these routing invariants.

## Discipline

Press's discipline is evidence-first: fear is the curd-killer, and an
unverified failure is not a RED. Before each route decision, name the outcome,
the attack digest, and the completed `repair_cycles` count. If any one is
missing, stop rather than guessing.
