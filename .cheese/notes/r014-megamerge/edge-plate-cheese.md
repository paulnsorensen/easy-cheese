# Plate to Cheese edge review

## State

broken

## Evidence

- The only direct edge is the shared question transport.
  Plate links that transport at `skills/plate/references/topology.md:27-50`.
  Cheese defines it at `skills/cheese/references/ask-user-question.md:3-25,57-68`.
- Plate supplies `id`, `prompt`, `recommended`, `multi`, and two options at `skills/plate/references/topology.md:37-50`.
  Cheese requires those fields at `skills/cheese/references/ask-user-question.md:6-25`.
- Plate asks before mutation for a stack recommendation or ambiguous shape at `skills/plate/references/topology.md:27-31`.
  Cheese states the same rule at `skills/cheese/references/coherence-check.md:33-37`.
- Plate keeps this question under `--auto` at `skills/plate/references/topology.md:33-35`.
  Cheese forbids automatic state changes at `skills/cheese/references/ask-user-question.md:116-123`.
- Plate persists only `plate_layout: single | stacked` at `skills/plate/references/topology.md:57-61`.
  Cheese can return a free-form `other:` value at `skills/cheese/references/ask-user-question.md:125-134`.
- Plate has no runtime call, import, command, emitted file, or handoff field for Cheese.
  Its command surface imports only shared and Plate modules at `src/easy_cheese/skills/plate/commands.py:8-29`.
- Plate tests check the transport link at `tests/python/test_plate_contract.py:13-49`.
  Cheese tests check the generic transport at `tests/python/test_docs_emphasis_guard.py:175-258,291-296`.
- The transport audit accepts any file-level link at `tests/python/test_transport_audit.py:51-74,186-195`.
  It does not validate the Plate record.
- The focused test set reports 36 passes.
  An in-memory probe removed `prompt` and changed `multi` to `true`.
  The current Plate and transport seam assertions still passed.

## Findings

### Blocker

none

### High

- **[spec:high] The Plate summary in Cheese omits one required question.**
  Plate asks when it recommends a stack or finds ambiguous shape at `skills/plate/references/topology.md:27-31`.
  Cheese only names ambiguous shape at `skills/cheese/SKILL.md:190-193`.
  Cheese gives the complete rule elsewhere at `skills/cheese/references/coherence-check.md:33-37`.
  **Fix:** Make `skills/cheese/SKILL.md` state both triggers.
- **[correctness:high] Plate does not handle the required `Other` answer.**
  Cheese preserves `Other` and returns `other:` at `skills/cheese/references/ask-user-question.md:22-25,95-114,125-134`.
  Plate accepts only `single | stacked` at `skills/plate/references/topology.md:57-61`.
  The caller can guess, persist invalid state, or stop without a defined error.
  **Fix:** Map only unambiguous text to an option identifier.
  Ask one clarification for all other text.
  Persist only `single` or `stacked`.
- **[assertions:high] Tests do not exercise the seam from both sides.**
  The Plate test checks phrases and the link at `tests/python/test_plate_contract.py:13-49`.
  The Cheese test checks only its generic transport at `tests/python/test_docs_emphasis_guard.py:175-258,291-296`.
  The mutation probe proves that both checks accept an invalid Plate record.
  **Fix:** Parse the Plate record and validate every field.
  Test `single`, `stacked`, `other:`, ambiguous answers, and `--auto`.

### Medium

none

### Low

none

## STE100 status

This note is compliant.
The reviewed edge prose is not compliant.

- `skills/plate/SKILL.md:20` puts two instructions in one sentence.
- `skills/plate/references/topology.md:18` puts two instructions in one sentence.
- `skills/cheese/SKILL.md:120` puts multiple instructions in one long sentence.
- `skills/cheese/references/ask-user-question.md:131-132` puts two instructions in one sentence.

Fix each listed sentence.
Use one instruction per sentence.

## Follow-ups

- Align the Cheese Plate summary with both question triggers.
- Define Plate behavior for a normalized `other:` answer.
- Add two-sided tests for the record, normalization, and `--auto`.
