# Cure to Plate edge review

## State

broken

## Evidence

- **Name and flags:** Cure calls `/plate` after a clean cure at `skills/cure/SKILL.md:94-100,119-122`.
- Cure passes `--hard` unchanged at `skills/cure/SKILL.md:227-234`.
- Plate accepts `--hard` at `skills/plate/SKILL.md:45-46`.
- **Request type:** No typed request crosses this edge.
- The contract uses a skill dispatch and the current repository state.
- **Handoff fields:** Cure emits `status`, `next`, `artifact`, and `baseline` at `skills/cure/SKILL.md:135-170`.
- Plate does not consume the Cure report.
- Plate validates its terminal JSON at `src/easy_cheese/skills/plate/publication.py:14-19,59-174`.
- That JSON requires `mode`, `topology`, `provider`, `artifacts`, `gate`, `commits`, `prs`, and `risk`.
- **Defaults:** Cure updates an open pull request by default at `skills/cure/SKILL.md:186-204`.
- `--open-pr` authorizes a new pull request before Cure dispatches Plate.
- Plate selects the existing or new pull request mode at `skills/plate/SKILL.md:27-46`.
- **Errors:** Cure skips Plate when the cure is not clean at `skills/cure/SKILL.md:203-207`.
- Plate reports the mode, failed step, and error owner at `skills/plate/SKILL.md:109-123`.
- Plate reports completion only after `valid: true` at `skills/plate/SKILL.md:125-155`.
- **Commands and imports:** No Python import or bundle command crosses this edge.
- Cure imports only shared commands at `src/easy_cheese/skills/cure/commands.py:7-96`.
- Plate exposes `stack-tools` and `validate-publication` at `src/easy_cheese/skills/plate/commands.py:8-34`.
- **Suppression:** Cure returns control to Affinage at `skills/cure/SKILL.md:190-194`.
- Cook workers also suppress Plate at `skills/cure/references/auto-mode.md:29-33,46-64`.
- **Tests:** The focused Plate and Hard Cheese tests passed with 51 tests.
- `tests/python/test_plate_contract.py:337-344` reads only Cure prose for its cross-skill policy test.
- `tests/python/test_hard_cheese.py:156-166` checks `--hard` on both sides.
- `tests/python/test_plate_runtime.py:36-110` checks Plate terminal validation only.

## Findings

### Blocker

none

### High

- **Cure writes tracked facts after Plate publishes.** Cure starts write-back after publication at `skills/cure/SKILL.md:205,221-246`.
  Its fallback writes tracked files at `skills/cure/references/post-pr-writeback.md:16-41`.
  Plate requires every durable write before validation and commit at `skills/plate/SKILL.md:63-76`.
  Plate also forbids later wiki publication at `skills/plate/SKILL.md:69-72`.
  Plate changed the final writing contract, but Cure did not follow its required order.
  **Fix:** Move the write-back before Cure dispatches Plate.
  Give each write to Plate through its artifact inventory.
  Do not write tracked files after Plate completes.

### Medium

- **The core dispatch contract lacks paired tests.** The open-pull-request test reads Cure only at `tests/python/test_plate_contract.py:337-344`.
  The test does not check clean gating, write order, Plate failure, or publication ownership.
  The Hard Cheese tests cover only `--hard` at `tests/python/test_hard_cheese.py:156-166`.
  **Fix:** Add paired tests for clean dispatch, unclean suppression, write order, Plate failure, and all publication flags.

### Low

none

## STE100 status

- `skills/cure/SKILL.md` is not compliant.
  Lines 31, 205, 221, 236, and 246 use inconsistent terms.
  Line 45 lacks sentence capitalization.
  Line 116 uses the passive voice.
- `skills/plate/SKILL.md` is not compliant.
  Lines 4-8 use both `pull request` and `PR`.
  Lines 23, 53, and 63 use the passive voice or combine instructions.
  Lines 65 and 112 use different terms for the quality gate.

## Follow-ups

- Move Cure post-PR write-back before Plate. Add each output to Plate's artifact inventory.
- Add paired tests for clean dispatch, unclean suppression, write order, Plate failure, and all publication flags.
- Rewrite both skill files in Simplified Technical English.
