---
name: press
description: Run the tests-only adversarial gate after `/cook`, preserving the outer oracle and routing bounded corrective Cook continuations. Use when the user says "press the changes", "harden this", "press before /age", or "/press". Do NOT edit production code or dispatch a global Cook repair from Press.
license: MIT
---

# /press

Press is the tests-only adversarial gate after `/cook`. Its skill-level
contract is:

```text
press(spec_ref, original_receipt)
  -> Continue("press-corrective-cook")
   | Dispatch("/age")
   | Stop(gated_evidence)
```

`original_receipt` is the RED receipt issued by Cut and made GREEN by Cook.
Press never owns first coverage and never edits production code. Cut and Cook
own the outer oracle and implementation; Press only attacks the approved
contract and preserves evidence for a fresh bounded Cook repair.

## Packaged commands

Resolve every `red-gate ...` invocation through
[`../cut/references/gate-workflow.md`](../cut/references/gate-workflow.md)
§ Packaged command resolution. For boundary routing, append
`press-route .cheese/press/<slug>.attempt-N.route.json` to `python3
${CLAUDE_SKILL_DIR}/scripts/press.pyz`; in a source checkout use
`python3 skills/press/scripts/press.pyz press-route
.cheese/press/<slug>.attempt-N.route.json`. The request has exactly
`outcome`, `current_receipt`, `phase_token_ref`, and `phase_token_sha256`:

```json
{
  "outcome": "green",
  "current_receipt": ".cheese/cut/<slug>.json",
  "phase_token_ref": ".cheese/press/<slug>.attempt-1.phase.json",
  "phase_token_sha256": "<64 lowercase hex characters>"
}
```

The boundary replays the current receipt, validates and consumes the one-use
Press phase token, derives production changes from its snapshot and declared
`production_paths`, reconciles the durable journal with immutable receipts, and
derives the completed repair count. Caller-supplied `repair_cycles`,
`completed_cycles`, or `production_changed` fields are forbidden. The command's
JSON action is authoritative. Halt if neither bundle exists.

Each Press attempt has its own append-only artifact names. Use the same
`<slug>` for all three attempts, but never reuse an attempt number:

| Press attempt | phase plan | phase token | candidate | receipt | route request |
| --- | --- | --- | --- | --- | --- |
| P1 (`attempt-1`) | `.cheese/press/<slug>.attempt-1.plan.json` | `.cheese/press/<slug>.attempt-1.phase.json` | `.cheese/press/candidates/<slug>.attempt-1.json` | `.cheese/press/<slug>.attempt-1.json` | `.cheese/press/<slug>.attempt-1.route.json` |
| P2 (`attempt-2`) | `.cheese/press/<slug>.attempt-2.plan.json` | `.cheese/press/<slug>.attempt-2.phase.json` | `.cheese/press/candidates/<slug>.attempt-2.json` | `.cheese/press/<slug>.attempt-2.json` | `.cheese/press/<slug>.attempt-2.route.json` |
| P3 (`attempt-3`) | `.cheese/press/<slug>.attempt-3.plan.json` | `.cheese/press/<slug>.attempt-3.phase.json` | `.cheese/press/candidates/<slug>.attempt-3.json` | `.cheese/press/<slug>.attempt-3.json` | `.cheese/press/<slug>.attempt-3.route.json` |

For each row, write a phase plan whose `production_paths` exactly equal the
current receipt's bound phase-token roots—the exact roots the corrective Cook
may mutate—then run
`red-gate begin <phase plan> --out <phase token>` before the attack. Run
`red-gate issue <candidate> --token <phase token> --out <receipt>` only when
the attack is RED. Put each route request in that row's route path and include
that row's token ref and digest. For RED, set `current_receipt` to the new
receipt from that row: P1 carries P1, P2 carries P2, and P3 carries P3. For
GREEN, no new receipt exists: set `current_receipt` to the latest receipt that
existed at phase entry—P1 uses the original Cut receipt, P2 uses P1, and P3
uses P2. Never point a GREEN route at the unissued receipt path from its row.
Routing requires canonical phase-token encoding and writes an immutable
decision keyed by the token digest, so copied or reformatted evidence cannot
create a second interval and the same interval cannot be routed twice. Route
files are attempt-qualified input, not receipts, and must not be reused. A P3
RED routes to terminal
`Stop("third-red")`; do not create P4 names or overwrite any earlier path.

## Entry and evidence contract

Before the first adversarial attack, Press MUST:

1. Resolve the approved `spec_ref` and the original Cut receipt.
2. Replay the original receipt with `red-gate validate <receipt> --state green`.
3. Verify every protected oracle digest from that receipt.
4. Write the strict Press phase plan with exact project-relative
   `production_paths`, then run `red-gate begin` before adding an attack.
   Preserve its phase-token ref and digest for both the candidate and route.

An invalid, stale, unchained, or digest-mismatched receipt is an evidence
failure. It stops Press; it is never converted into a RED repair request.

Press runs a fresh `red-gate begin` at every Press entry and every post-Cook
resume, before adding or changing an attack. That token freezes all
non-production oracle dependencies plus the production roots and entry
baselines for exactly one Press-owned interval. `red-gate issue` allows only
the candidate's exact protected test-side changes from that token. The route
boundary independently derives whether a declared production root changed and
consumes the token once; a production change is an ungated stop, not a repair.
Never reuse a token from an earlier attack, resume, or route decision.

## Adversarial loop

1. **Attack** — add or run only tests, fixtures, and test-only harness support
   against the same approved seam and witness. Keep the attack identity and
   failing-test digest stable.
2. **Issue** — an in-contract failure goes through `red-gate issue` only,
   using the current row's attempt-qualified candidate, phase token, and
   receipt paths above. The candidate carries the fresh token ref/digest,
   preserves the failing test digest, guards the original Cut receipt, and
   transitively guards every prior Press receipt.
3. **Repair** — the route boundary replays the current receipt, reconciles the
   authoritative journal with the complete immutable Press-receipt graph, and
   derives `completed_cycles`. The current Press RED is excluded; earlier Press
   RED receipts are completed corrective continuations. P1 has
   `completed_cycles=0` and returns `Continue`; P2 has `completed_cycles=1`
   and returns `Continue`; P3 has `completed_cycles=2` and returns terminal
   `Stop("third-red", gated_evidence=True)`.
4. **Replay** — after Cook returns, replay the identical attack with the same
   attack/test digest and start a new production snapshot interval.
5. **Terminate** — GREEN returns the only global dispatch,
   `Dispatch("/age")`; no fourth Press receipt is issueable.

Invalid or unchained evidence and any production-tree mutation return a gated
false stop. They do not return a continuation. Press has no global
`dispatch: /cook` action; the corrective Cook is a Press-owned `Continue`
action only.

## Baseline-aware gates

Press preserves baseline-aware readiness behavior for project gates. A Cook `baseline:` block is settled state: failures with the same test and signature do not re-flag or re-halt; new or changed failures remain blocking. Baselines never override receipt, digest, guard, or repair-cycle invariants. See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md) and [`references/gap-analysis.md`](references/gap-analysis.md).

## Flow

1. **Read** — load the approved spec, Cut receipt, Cook handoff, and any
   baseline block. If `.cheese/glossary/<slug>.md` exists, use its canonical
   terms.
2. **Protect** — validate the original receipt GREEN and verify protected oracle
   digests. Write the Press plan and run `red-gate begin` before any attack.
3. **Attack** — add or run adversarial tests only; do not add first-coverage
   tests or alter production paths.
4. **Issue or classify** — route an in-contract RED candidate through the
   token-bound `red-gate issue`; classify GREEN, invalid evidence, and
   production changes without writing raw receipt JSON.
5. **Continue or stop** — invoke packaged `press.pyz press-route` with
   `outcome`, `current_receipt`, and the current phase token ref/digest. The
   boundary rejects missing, reused, cyclic, symlinked, escaping, stale,
   journal-divergent, cross-work/spec/project, or production-mutating evidence
   before routing. Only its returned `Continue`, `Dispatch`, and `Stop` action
   shapes are public.
   public.
6. **Report** — write `.cheese/press/<slug>.md` with the evidence and action.
7. **Hand off** — only a GREEN `Dispatch("/age")` reaches the global Age route.

Compatibility contracts: source changes follow [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md). Portability follows [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md); slash commands are host renderings, not the control model. Readiness `ready for /age` maps to `status: ok` and `next: age`; `blocked` or `follow-up recommended` maps to `status: halt`. When invoked from `/ultracook` with its no-chain directive, write the Press handoff and stop; do not chain forward.

## Receipt invariants

- `red-gate issue` is the only receipt writer. Press MUST NOT publish a raw or
  hand-written `GateReceipt`.
- Every newly issued Press receipt carries the fresh entry token ref and digest;
  a token from a prior Press interval or different work/project fails closed.
- A phase token is consumed by exactly one route decision. Reusing it for a
  second RED or GREEN classification fails closed.
- Every Press RED receipt has `producer: press`.
- Its `guard_receipt_refs` include the original Cut receipt and every earlier
  Press receipt, transitively and without duplicate or cyclic references.
- The active failing test and its digest remain unchanged across every fresh
  corrective Cook and identical-attack replay.
- Protected oracle files and all non-production dependencies remain
  digest-identical; the route boundary derives changes under every declared
  production root from the phase-token snapshot instead of trusting the caller.
- Invalid, stale, shell-shaped, path-escaping, witness-inconsistent, or
  unchained evidence halts without a repair action.
- The durable Press history records at most P1, P2, and P3 for one
  project/work identity. P1 must guard Cut and returns `Continue` with
  `completed_cycles=0`; P2 must guard P1 transitively and returns `Continue`
  with `completed_cycles=1`; P3 must guard P1 and P2 transitively and may
  record the terminal third-RED stop with `completed_cycles=2`. P4 and any
  truncated chain fail closed.

## Output

Write `.cheese/press/<slug>.md` with this minimum handoff shape:

```markdown
status: ok | halt: <one-line reason>
next: age | press | done
artifact: <receipt-or-evidence-path>
baseline: none | <Cook baseline block>
action: continue | dispatch | stop
<one-line orientation>
```

Project the router action without inventing a runnable phase:

| router action | status | next | action |
| --- | --- | --- | --- |
| `Dispatch("/age")` after GREEN | `ok` | `age` | `dispatch` |
| `Continue("press-corrective-cook")` on repair cycle 0 or 1 | `ok` | `press` | `continue` |
| `Stop("third-red", gated_evidence=True)` | `ok` | `done` | `stop` |
| invalid evidence or production change | `halt: <reason>` | `done` | `stop` |

`next: done` is terminal and never auto-dispatches. A valid third-RED stop may
offer a later user-selected Cook handoff, but it does not encode Cook, Press,
or Age as its next phase. Invalid evidence and production changes halt.
`next: age` is reserved for GREEN `Dispatch("/age")`; a corrective `Continue`
is Press-owned and is not a global phase handoff.

## Handoff

**Pipeline:** culture → mold → cut → cook → **[press]** → age → cure → plate

After a GREEN Press report, use the shared [handoff gate](../cheese/references/handoff-gate.md) to review with `/age <slug>`. A Press corrective Cook continuation is driven internally by
the Press owner and is not offered as a second global route. `--hard` remains
pass-through to `/age` and later phases.

## Rules

- Do not weaken or replace the Cut oracle, its guards, its witness, or its
  protected files.
- Do not edit production code, production fixtures, or production adapters.
- Do not publish raw receipt JSON or issue evidence outside `red-gate issue`.
- Do not dispatch a global Cook repair from Press.
- Do not exceed two corrective continuations or change the attack between
  retries.
- Do not treat out-of-contract desired behavior as an implementation request;
  record it as a follow-up for review.
- Preserve existing baseline-aware hardening/readiness behavior where it is
  not superseded by these receipt and routing invariants.

## Discipline

Press's discipline is evidence-first: fear is the curd-killer, and an
unverified receipt is not a RED. Before each route decision, name the outcome,
the canonical current receipt and its validated chain, the derived
`completed_cycles` value, attack digest, and production digest boundary.
If any one is missing, stop rather than guessing.
