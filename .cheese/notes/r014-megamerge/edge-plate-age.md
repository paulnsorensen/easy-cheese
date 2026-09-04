# Plate to Age Edge Review

## State

untested

The contract text agrees at HEAD.
Plate assigns code-quality review to Age.
Plate does not call Age or consume an Age artifact.
The tests cover only the Plate side.

## Evidence

| Contract part | Plate evidence | Age evidence | State |
| --- | --- | --- | --- |
| Route name | `skills/plate/SKILL.md:18-24` assigns code-quality review to `/age`. | `skills/age/SKILL.md:2-7` names Age and accepts code-review requests. | ok |
| Input type | `skills/plate/evals/evals.json:124-127` supplies a branch review request. | `skills/age/SKILL.md:31-35` accepts a range or the current diff. | ok |
| Required fields | `src/easy_cheese/skills/plate/commands.py:11-30` defines no Age command or payload. | `skills/age/SKILL.md:31-35` requires no input for a current-diff review. | ok |
| Defaults | `skills/plate/SKILL.md:18-24` routes review work before mode selection. | `skills/age/SKILL.md:34-35` defaults to the current diff and repository base. | ok |
| Error mode | `skills/plate/SKILL.md:109-123` reports an Age request as a Plate routing error. | `skills/age/SKILL.md:183-187` halts when evidence is unavailable. | ok |
| Emitted files and fields | `src/easy_cheese/skills/plate/publication.py:18-19,59-69` permits no Age report field. | `skills/age/SKILL.md:151-188` writes the Age report for Cure. | ok |
| Commands | `src/easy_cheese/skills/plate/commands.py:11-30` exposes only `stack-tools` and `validate-publication`. | `src/easy_cheese/skills/age/commands.py:25-36,53-64` owns review routing, surface, lock, and report commands. | ok |
| Tests | `tests/python/test_plate_contract.py:183-192,278-304` checks the Plate route and its evaluation case. | No Age test checks this route or its default input. | untested |

The Plate source has no Age import, handoff field, file, or command.
Age sends its report to Cure, not back to Plate.
No unilateral contract change exists at HEAD.

## Findings by severity

### Blocker

none

### High

none

### Medium

- **[assertions:medium] The ownership edge has only Plate tests.** `tests/python/test_plate_contract.py:183-192,278-304` checks Plate. `skills/age/SKILL.md:2-7,31-35` defines the consumer behavior without a matching test. Add one cross-skill contract test. Verify `/age`, the current-diff default, and the Plate classify error.

### Low

- **[deslop:low] One Plate sentence contains two instructions.** `skills/plate/SKILL.md:20` prohibits review and review-surface work in one sentence. Split the prohibitions into two sentences.

## STE100 status

- `skills/plate/SKILL.md:20` needs one instruction per sentence.
- The Age edge prose is compliant.
- This note is compliant.

## Follow-ups

- Add one cross-skill contract test for the Plate to Age route.
- Split the two Plate prohibitions into separate sentences.
