# Cure to Hard-cheese Edge Review

## State

broken

Cure forwards the flag correctly, but Cure and hard-cheese disagree about the `ERROR` outcome.

## Evidence

- `skills/cure/SKILL.md:38,198-200,214,227-234` defines `--hard` as optional and forwards it only to `/plate`.
- `skills/cure/references/auto-mode.md:22-39` forwards `/plate --hard` and prohibits a direct `/hard-cheese` call.
- `src/easy_cheese/skills/cure/commands.py:1-97` has no direct hard-cheese import, command, emitted file, or handoff field.
- `skills/plate/SKILL.md:45-46` runs `/hard-cheese` at the publication boundary and supplies the final artifact inventory.
- `skills/plate/references/durable-writes.md:42-61` defines required rows as `{target, backend, verified}` and includes the tracked diff and gate result.
- `skills/hard-cheese/SKILL.md:25-36,58-88,90-119` defines the Plate input, result statuses, and `.cheese/hard-cheese/<slug>.md` output.
- `skills/hard-cheese/references/composition.md:15-40` defines inactive, commit-only, non-TTY, and automatic behavior at one execution point.
- `src/easy_cheese/skills/hard_cheese/commands.py:14-35` exposes only `append-attempt` and `freshness-check`. It has no Cure-specific adapter.
- `tests/python/test_hard_cheese.py:156-166` checks the Cure producer and the Plate bridge.
- `tests/python/test_hard_cheese.py:246-285,299-310` checks non-TTY text, one execution point, and the automatic Cure section.
- `uv run pytest -q tests/python/test_hard_cheese.py -k 'cure or plate or composition or non_tty or single_puncture'` passed eight tests.

## Findings

### Blocker

none

### High

- **[spec] Cure and hard-cheese define different `ERROR` behavior.** `skills/cure/SKILL.md:232` permits publication only after `PASS`. `skills/hard-cheese/SKILL.md:78,148-155,177` returns zero for `ERROR` and permits publication. Plate defines no mapping between these policies. **Fix:** Make Cure stop only for `FAILED` and non-TTY errors. State that `ERROR` uses the hard-cheese fail-open policy.

### Medium

- **[assertions] The seam tests protect only route text.** `tests/python/test_hard_cheese.py:156-166` checks producer and Plate sentences. Lines 246-285 check broad terms. No test binds `PASS`, `FAILED`, `ERROR`, or non-TTY behavior to Plate publication. **Fix:** Add a parameterized contract test for all four outcomes.

### Low

none

## STE100 status

- This note is compliant.
- `skills/cure/SKILL.md:31,45,116,205,221,236,246` still violates active-voice, capitalization, and consistent-term rules.
- `skills/hard-cheese/SKILL.md:30,32,47,127,157,197` still uses multiple gate terms and compound instructions.
- `skills/hard-cheese/references/composition.md:13,17,37,39` still uses multiple gate terms and compound instructions.

## Follow-ups

- Align Cure with the hard-cheese `ERROR` policy.
- Add the hard-gate outcome matrix test.
- Apply the recorded STE100 corrections in the Cure and hard-cheese prose.
