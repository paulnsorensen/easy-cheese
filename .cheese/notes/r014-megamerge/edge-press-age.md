# Press to Age Edge Review

## State

broken

Press reaches Age after a green route.
The durable report loses required Press context at the Age reader.

## Evidence

- Producer prose permits `Dispatch("/age")` only after `green` (`skills/press/SKILL.md:74-80,94-101`).
- The producer defaults the dispatch command to `/age` (`src/easy_cheese/shared/fanout/press_route.py:26-30,74-87`).
- The producer CLI serializes `action` and `command` (`src/easy_cheese/shared/fanout/press_route_cli.py:15-35`).
- The Press report puts `action:` and `telemetry:` before orientation (`skills/press/SKILL.md:114-143`).
- Age reads the Press handoff with `read-handoff-slug` (`skills/age/SKILL.md:92-99`).
- Age must summarize unresolved Press items in `## Press findings` (`skills/age/SKILL.md:93-95,151-160`).
- The reader returns metadata only (`src/easy_cheese/shared/read_handoff_slug.py:17-40`).
- The parser accepts only `taste_test:`, `durable_flags:`, and `baseline:` before orientation (`src/easy_cheese/shared/handoff.py:105-161`).
- The phase registry declares the `press` to `age` route with the Curd result schema (`skills/press/phase-contract.yaml:5-10`).
- The producer route test checks the green Age dispatch (`tests/fanout/python/test_press_route.py:79-91`).
- The seam test checks the canonical paths and basic fields (`tests/shared/python/test_handoff_roundtrip_integration.py:268-326`).
- The seam test omits the Press-specific `action:`, `telemetry:`, and report body fields (`tests/shared/python/test_handoff_roundtrip_integration.py:301-325`).
- The focused test command passed all 33 tests in the producer, reader, and round-trip files.
- An actual bundle probe returned `orientation: "action: dispatch"` for the documented Press report shape.
- The reconciliation notes report no changed route name or type (`.cheese/notes/r014-megamerge/press.md:20-30`; `.cheese/notes/r014-megamerge/age.md:34-45`).

## Findings

### Blocker

none

### High

- **The Age reader silently changes the Press orientation.** Press places `action:` and `telemetry:` before the orientation. The canonical parser treats the first unknown keyed line as orientation. Age then loses the intended orientation and telemetry reference. Move both Press-specific fields into the report body. Add `write-handoff-artifact` to the Press bundle. Produce the preamble with the canonical writer.
- **Age cannot read the Press findings that its contract requires.** Age invokes a preamble-only reader, but then requires a summary of unresolved Press items. Press also requires out-of-contract findings to reach Age (`skills/press/SKILL.md:155-162`). Define a `## Review follow-ups` section in the Press body. Validate the preamble first. Then read the complete report through the selected file reader.

### Medium

- **The tests do not exercise the documented report shape.** The route test verifies `/age`. The round-trip test uses only canonical preamble fields. Add one test that writes the complete Press report and reads it through the Age bundle. Assert the real orientation, telemetry path, baseline, and review follow-ups.

### Low

- **The Age usage text omits `--hard`.** Press requires this flag at `skills/press/SKILL.md:145-153`. Age describes the flag at `skills/age/SKILL.md:40-42`, but omits it from lines 19-22. Add `[--hard]` to both Age usage forms.

## STE100 status

compliant

The edge prose in both skill files uses short, active instructions.
The reconciliation notes also mark both complete prose audits as compliant.
