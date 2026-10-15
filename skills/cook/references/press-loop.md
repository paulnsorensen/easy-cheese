# Press loop

Cook owns the Press loop for behavior work.
Press is the adversarial pass that Cook dispatches automatically.
The user never selects Press from a menu.
Non-behavior work skips the Press loop.

## Dispatch

After the taste test passes, Cook dispatches a fresh-context Press agent.
Resolve the agent through [`../../cheese/references/agent-resolution.md`](../../cheese/references/agent-resolution.md).
Use the coder role with writes limited to tests.
The spawn prompt carries the no-chain directive from [`auto-mode.md`](auto-mode.md).
Press writes `.cheese/press/<slug>.md` and returns to Cook.
See [`../../press/SKILL.md`](../../press/SKILL.md) and [`../../press/references/gap-analysis.md`](../../press/references/gap-analysis.md).

## Outcomes

| Press outcome | Cook action |
| --- | --- |
| `green` | Hand off to Age. |
| `finding` | Run a correction (`correction = true`). Press replays the same attack. |
| `coverage_gap` | Run a coverage addition (`correction = true`). Press reruns. |
| `invalid_evidence` or `production_changed` | Halt with `halt: invalid-evidence` or `halt: production-changed`. |

A correction fixes only the reported finding. A coverage addition adds first acceptance coverage only. It makes no production change beyond what that coverage exposes.

## Caps

Cook is the single round counter. Press has no memory across fresh dispatches.
Cook records each round in the package report's `### Press loop` section.
Cook passes the round number and the attack identity in each dispatch.
Press emits a halt only from that round number.

- A correction runs at most 2 times for one attack. A third finding halts with `halt: correction-cap`.
- A `coverage_gap` retries once. A second `coverage_gap` in one Cook run halts with `halt: coverage-gap`.

Each halt reports `next: done`.
Cook never publishes `next: press`.

## Report

Record each round in the package report's `### Press loop` section.
Link `.cheese/press/<slug>.md`.
