# Plate review

## Verdict

reject

Plate has three high findings and two medium findings.
The Plate area also has seven prose files that do not comply with STE100.
Focused tests passed: 37.
A 503 probe confirmed that `stack-tools` loses response details.

## Blocker

none

## High

- **[spec:high] Plate and `/gh` both claim pull request creation.** `skills/plate/SKILL.md:5-8,18-23` gives Plate exclusive creation ownership. `skill://gh:5-12` routes pull request creation to `/gh`. A direct `/gh` route can skip Plate's durable write and quality gates. **Fix:** Give Plate exclusive creation routing. Limit `/gh` to inspection and administration.
- **[spec:high] `stack-tools` discards required service-error evidence.** `src/easy_cheese/skills/plate/stack_tools.py:61-83,116-145` returns only a category and repository signal. `skills/plate/references/gh-stack.md:61-72,95-109` requires the HTTP status and stderr. A 503 probe returned only `('service-error', None)`. **Fix:** Return the HTTP status, exit status, and stderr. Add exact tests for these fields.
- **[assertions:high] The stack recovery test accepts a prohibited Git recovery command.** `tests/python/test_plate_contract.py:101-108` checks only that each reference contains `git rebase --continue`. The test passes when a reference tells the agent to run that command. **Fix:** Require the exact prohibition and the exact provider recovery command for each provider.

## Medium

- **[spec:medium] The routing guard and mode table give different routes for inspection.** `skills/plate/SKILL.md:20-24` routes read-only inspection away from Plate. `skills/plate/SKILL.md:37` classifies stack inspection as Plate stack maintenance. **Fix:** Limit the table trigger to inspection that supports a requested stack change.
- **[spec:medium] New pull request mode conflicts with the one-reference rule.** `skills/plate/SKILL.md:29,35,39-43` first forbids other references. It then requires a topology-selected execution reference and a provider reference. **Fix:** Require one reference at a time. Name the required reference sequence.

## Low

- **[deslop:low] `SKILL.md` breaks the area prose rules.** `skills/plate/SKILL.md:23,35,53,63,92,101` uses passive voice or gives multiple instructions. Lines 4-8 use both `pull request` and `PR`. Lines 65 and 112 use different terms for the quality gate. **Fix:** Use active voice. Split each instruction. Define `PR` once or use `pull request`. Use `quality gate` throughout.
- **[deslop:low] The generated command reference uses a second repository term.** `skills/plate/references/commands.md:7` says `repo`. Other Plate prose says `repository`. **Fix:** Change the command summary in `src/easy_cheese/skills/plate/commands.py:26-29`. Regenerate the reference.
- **[deslop:low] The durable write reference combines instructions.** `skills/plate/references/durable-writes.md:3-4,39` combines write, read, and retry actions. **Fix:** Put each instruction in a separate sentence.
- **[deslop:low] The `gh stack` reference uses passive voice and compound instructions.** `skills/plate/references/gh-stack.md:3-4,23,30-44,64-67,100` contains the violations. **Fix:** Use active voice. Put each instruction in a separate sentence.
- **[deslop:low] The ordinary pull request reference breaks prose and list rules.** `skills/plate/references/ordinary-pr.md:20,41,46,63` restarts a list, uses passive voice, and combines instructions. Line 3 calls the quality gate a project gate. **Fix:** Continue the list. Use active voice. Split the instructions. Use `quality gate`.
- **[deslop:low] The stack reference breaks prose and term rules.** `skills/plate/references/stacks.md:3-5,9,19,21,33,46,56` uses passive voice, compound instructions, and ambiguous `ship` terminology. **Fix:** Use active voice. Split the instructions. Use `merge` only for merge operations.
- **[deslop:low] The topology reference uses passive voice and compound instructions.** `skills/plate/references/topology.md:18,33,40,54,61` contains the violations. **Fix:** Use active voice. Put each instruction in a separate sentence.

## Simplifications

- Replace “load only one reference” with “load one reference at a time.”
- Remove `inspect` from the stack maintenance trigger. Keep inspection as a transaction step.
- Move `tests/python/test_plate_contract.py:307-345` to the Cook and Ultracook compatibility tests. The tests read retired or foreign contracts.
- Keep `_http_status` and `_gh_stack_enablement`. Each helper hides a separate protocol rule.
- Change `ordinary-pr.md:20` to list step 7.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `plate -> shared` | ok | `commands.py:8-34` uses `bundle_command`, `derive_command`, and `dispatch`. `bundle_commands.py:61-83,138-154` provides matching signatures. The focused tests passed. |
| `plate -> age` | ok | `skills/plate/SKILL.md:20-24` delegates code review. `skills/age/SKILL.md:57-74` owns the review dimensions. |
| `plate -> gh` | broken | `skills/plate/SKILL.md:5-8,18-23` claims creation ownership. `skill://gh:5-12` also routes creation to `/gh`. |
| `plate -> wiki-ingest` | ok | `durable-writes.md:17-24` delegates wiki curation. `skill://wiki-ingest:2-15` owns ingest and update behavior. |
| `plate -> hard-cheese` | ok | `skills/plate/SKILL.md:45-46` sends final evidence. `skills/hard-cheese/SKILL.md:29-32,62` accepts the same boundary and rows. |
| `plate -> cheese` | ok | `topology.md:27-50` supplies one choice record. `ask-user-question.md:22-33,57-68` accepts that record and visible context. |
| `plate -> cook` | ok | `topology.md:70-79` follows the repair topology. `quality-gates.md:73-82` defines its overlap rules and thresholds. |

## STE100 status

- `skills/plate/SKILL.md` needs active voice, one instruction per sentence, and consistent terms.
- `skills/plate/references/commands.md` needs one term for `repository`.
- `skills/plate/references/durable-writes.md` needs one instruction per sentence.
- `skills/plate/references/gh-stack.md` needs active voice and one instruction per sentence.
- `skills/plate/references/ordinary-pr.md` needs active voice, one instruction per sentence, and consistent quality gate terminology.
- `skills/plate/references/stacks.md` needs active voice, one instruction per sentence, and one term for merge operations.
- `skills/plate/references/topology.md` needs active voice and one instruction per sentence.

## Follow-ups

- Align pull request creation ownership between Plate and `/gh`.
- Preserve `gh stack` service-error evidence. Strengthen the recovery assertions.
- Resolve the inspection and reference-loading contradictions.
- Rewrite the seven prose files for STE100.
