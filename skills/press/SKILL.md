---
name: press
description: Run the tests-only adversarial pass after `/cook`. Report each defect as a finding for a Cook correction. Use this skill when the user says "press the changes", "harden this", "press before /age", or "/press". Do not edit production code.
license: MIT
---

# /press

Press is the tests-only adversarial pass after `/cook`. It reports a GREEN pass to `/age` and a finding to Cook.

Press never owns first coverage. Press never edits production code. Cook owns the implementation. Press attacks the approved contract and reports each defect it exposes.

## Phase entry

Run `python3 skills/press/scripts/press.pyz wheypoint-resolve --ref <slug>`.
`authoritative` uses the record; its `working_context` is the first batched `tilth_read`.
`not-found` proceeds cold; `legacy` shows its source and slug, then proceeds.
`gated`, `ambiguous`, and `error` stop and show the payload.
Show advisory `stale-commit` and `grounded-path-missing` findings.

## Inputs

Press accepts this invocation:

```text
/press <slug> [--auto] [--hard] [--open-pr]
```

After phase entry, Press reads `.cheese/cook/<slug>.md` for the Cook handoff.

`--auto` selects the autonomous chain. See `## Auto mode`.

`--hard` requests the optional final gate. Press forwards this flag to Age.

`--open-pr` is publication permission. Only the user supplies it. Press forwards this flag to Age. Press never adds it.

Press preserves the Cook `durable_flags:` value without change. Press ignores the Cook `taste_test:` value.

## Adversarial loop

1. **Attack** — Add or run only tests, fixtures, and test-only harness support. Use the approved seam and witness. Keep the attack identity and test digest stable.
2. **Classify** — Use `finding` when an attack test exposes a defect. Use `green` for a clean pass. Use `production_changed` when the attempt changed production paths. Use `invalid_evidence` when you cannot verify the evidence.
3. **Report** — Report each finding with its failing test. Hand it to Cook as a correction.
4. **Replay** — Replay the same attack after the correction returns. Use the same attack and test digest. Then classify the result again.
5. **Terminate** — Hand off to `/age` after GREEN.

Invalid evidence and a production tree change stop the run.

Press has no global `dispatch: /cook` action. A Cook correction runs only for a reported finding.

## Baseline-aware gates

Press preserves baseline-aware readiness for project gates. The Cook `baseline:` line names one artifact. That artifact holds the settled state.

Read the artifact through the `baseline:` path. Do not re-flag a failure when its test and signature match the artifact. New or changed failures block the route.

See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md). Also see [`references/gap-analysis.md`](references/gap-analysis.md).

## Flow

1. **Read** — Load the approved spec, Cook handoff, and baseline block. Use canonical terms from `.cheese/glossary/<slug>.md` when that file exists.
2. **Attack** — Add or run only adversarial tests. Do not add first-coverage tests. Do not change production paths.
3. **Classify** — Select `green`, `finding`, `invalid_evidence`, or `production_changed` from the adversarial run.
4. **Report** — Write `.cheese/press/<slug>.md`. Include the attempts, evidence, and review follow-ups.
5. **Hand off** — Send GREEN to `/age`. Send a finding to Cook as a correction.

Use [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md) for source changes.

Use [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md) for portability.
The reference states that slash commands are host renderings, not the control model.

Press reports one readiness value. Map `ready for /age` to `status: ok` and `next: age`.

Map `follow-up recommended` to `status: ok-with-concerns: <concern>` and `next: age`. Use this status for a GREEN pass that also records a review follow-up. Age owns each recorded concern.

Map `finding` to `status: ok-with-concerns: <defect>` and `next: cook`.

Map `blocked` to `status: gated: <decision>` and `next: done`. Stop after that status.

## Auto mode

`--auto` runs the same adversarial loop. It also selects the next phase without a user prompt.

Dispatch `/age <slug> --auto` after `ready for /age` or `follow-up recommended`. Add `--hard` when the user supplied it. Add `--open-pr` when the user supplied it.

Stop after `blocked`. Do not dispatch Age.

Honor the no-chain directive when the caller supplies it. Write the Press handoff and stop. Do not start another phase. Cook's fan pathway owns this directive. The retired `/ultracook` orchestrator previously owned it. Test for the directive itself. Do not test for the source name. See [`../cook/references/auto-mode.md`](../cook/references/auto-mode.md).

## Output

Write `.cheese/press/<slug>.md` at each Press result.

Write the file with `python3 skills/press/scripts/press.pyz write-handoff-artifact`; include one or more `--grounded <path[#start-end]>` arguments. Use the canonical preamble:

```text
python3 skills/press/scripts/press.pyz write-handoff-artifact \
  --slug <slug> --status <status> --phase press --next <next> \
  --artifact .cheese/cook/<slug>.md --orientation "<one-line orientation>" \
  --durable-flags "<preserved Cook value>" --baseline "<baseline artifact path>" \
  --grounded <path[#start-end]> --body-file <body-path>
```

```markdown
status: <canonical status field>
next: age | cook | done
artifact: .cheese/cook/<slug>.md
durable_flags: <preserved Cook value>
baseline: none | <baseline artifact path>
<one-line orientation>
```

The [handback contract](../cheese/references/handback-contract.md) defines the `status:` grammar. The preamble accepts no other keys. Put every Press value in the report body.

`artifact:` names the consumed Cook report. Do not put attack evidence on this line.

`baseline:` names the one artifact that Cook recorded. See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md).

Write these body sections under the preamble:

- `## Attempts` — one row for each attempt. Give the attempt number and outcome.
- `## Evidence` — the stable attack identity, the test digest, and the failing test for a finding.
- `## Review follow-ups` — each out-of-contract concern. Write `none` when the run records no concern. Age reads this section.

Map the outcome to the terminal preamble:

| outcome | status | next |
| --- | --- | --- |
| GREEN | `ok` | `age` |
| GREEN with a recorded concern | `ok-with-concerns: <concern>` | `age` |
| finding (an attack test exposes a defect) | `ok-with-concerns: <defect>` | `cook` |
| invalid evidence or production change | `halt: <reason>` | `done` |

`next: done` is terminal. It never starts another phase.

A `next: cook` handoff is a Cook correction (`correction = true`). Cook fixes the defect. Press then replays the same attack.

## Handoff

**Pipeline:** culture → mold → cook → **[press]** → age → cure → plate

After a GREEN Press report, use the shared [handoff gate](../cheese/references/handoff-gate.md). Start the review with `/age <slug>`.

After a finding, hand off to Cook as a correction with the failing test named in the report.

Forward `--hard`, `--auto`, and `--open-pr` to `/age` when the caller supplied them. Never add `--open-pr`.

## Rules

- Do not edit production code, production fixtures, or production adapters.
- Do not change the attack between replays.
- Do not treat out-of-contract behavior as an implementation request. Record it under `## Review follow-ups`. Report the run as `ok-with-concerns` on a GREEN pass.
- Preserve baseline-aware readiness.

## Discipline

Press uses evidence first. An unverified failure is not a finding.

Name the outcome before each handoff decision. Name the attack digest. Stop if one value is missing. Do not guess.

Generated bundle command inventory: [`references/commands.md`](references/commands.md).
