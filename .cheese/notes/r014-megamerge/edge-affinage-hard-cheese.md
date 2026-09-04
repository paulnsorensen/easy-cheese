# Edge Review: Affinage to Hard-cheese

## State

untested

The prose contract agrees at HEAD.
No test proves that Affinage forwards `--hard` to Plate.
The consumer tests start at Cure or Plate.

## Evidence

### Affinage producer

- `skills/affinage/SKILL.md:33,53` defines `--hard` as an optional presence flag.
- `skills/affinage/SKILL.md:105-109,204-205` sends `--hard` to terminal Plate after approved replies.
- `skills/affinage/SKILL.md:229-234` states that Plate runs Hard-cheese once after final artifact verification.
- `skills/affinage/references/auto-mode.md:24-25` preserves `--hard` on the automatic terminal Plate command.
- `skills/affinage/references/handoff-templates.md:42-56` also passes `--hard` to Cure as a command flag.
- That handoff uses four Cure-only fields.
- `handoff_context.source_skill` is the string `/affinage`.
- `source_report` is a report path string.
- `selection` is a selection string.
- `resolved_ids` is an identifier list.
- None of these fields enters Hard-cheese.
- `src/easy_cheese/skills/affinage/commands.py:42-59` lists the complete Affinage command surface.
- That surface has no Hard-cheese command, import, file, or direct call.

### Cure and Plate mediation

- `skills/cure/SKILL.md:190-194` uses `source_skill: /affinage` to prevent an early Plate call.
- `skills/cure/references/auto-mode.md:32-39` returns publication ownership to Affinage.
- The same text says a failed hard gate stops publication.
- It also defines the non-TTY error.
- `skills/plate/SKILL.md:45-46` consumes `--hard` and invokes Hard-cheese before publication.
- Plate supplies the final artifact inventory and verification rows.
- `skills/plate/references/durable-writes.md:44-61` defines each row as `{target, backend, verified}`.
- The Plate example uses strings for `target` and `backend` and a Boolean for `verified`.

### Hard-cheese consumer

- `skills/hard-cheese/SKILL.md:29-32` accepts propagated execution only from `/plate --hard`.
- `skills/hard-cheese/SKILL.md:20-23` defines the optional slug and gate defaults.
- The slug defaults to the short `HEAD` SHA.
- The retry cap defaults to `3`.
- The passing score defaults to `3`.
- `skills/hard-cheese/SKILL.md:60-69` consumes the diff summary, final inventory, and exact verification-row shape.
- `skills/hard-cheese/references/composition.md:19-23` runs no gate when terminal Plate does not publish.
- `skills/hard-cheese/references/composition.md:31-40` rejects non-TTY use and allows one gate with `--auto --hard`.
- `skills/hard-cheese/SKILL.md:73-88,159-177` defines PASS, FAILED, LOGGED, and fail-open ERROR results.

### Tests

- `tests/python/test_hard_cheese.py:147-166` tests Cure-to-Plate and Plate-to-Hard-cheese propagation.
- Its `PROPAGATION_SKILLS` list does not include `affinage`.
- `tests/python/test_plate_contract.py:347-367` checks that Affinage names Plate.
- It does not check that Affinage preserves `--hard`.
- `uv run pytest -q tests/python/test_hard_cheese.py tests/python/test_plate_contract.py` passed 51 tests.
- `uv run pytest -q tests/hard-cheese/python` passed 37 runtime tests.
- These passing suites do not exercise the Affinage source side.

## Findings by severity

### Blocker

none

### High

- **[assertions:high] The Affinage hard-gate edge has no regression test.**
  The suite passes if Affinage drops `--hard` from its terminal Plate command.
  Evidence: `tests/python/test_hard_cheese.py:147-166` and `tests/python/test_plate_contract.py:347-367`.
  **Fix:** Add one seam test that reads Affinage, Plate, and Hard-cheese contracts.
  Assert that Affinage sends `/plate --hard` after Cure returns.
  Assert that only Plate invokes Hard-cheese after final verification.

### Medium

none

### Low

none

## Contract drift

none

Both sides use the `--hard` name as an optional presence flag.
Their defaults, execution point, and failure modes agree.

## STE100 status

compliant

The reviewed edge prose and this note comply with ASD-STE100.
