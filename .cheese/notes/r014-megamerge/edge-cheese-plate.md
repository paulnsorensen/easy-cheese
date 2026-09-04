# Cheese to Plate edge review

## State

broken

`--hard` reaches Plate on the ordinary Cook path.
`--open-pr` does not survive every Cheese route.
The two skills also name different consumers for `--open-pr`.

## Evidence

- Cheese defines `--open-pr` and `--hard` as optional presence flags at `skills/cheese/SKILL.md:23-30`.
- Cheese requires exact dispatch commands with propagated flags at `skills/cheese/references/handoff-gate.md:56-75,180-189`.
- Cheese sends direct publication requests to `/plate` at `skills/cheese/SKILL.md:179-194` and `skills/cheese/references/classification.md:145-153`.
- Mold forwards only `--hard` at `skills/mold/SKILL.md:127-131`. A scoped search found no `--open-pr` in `skills/mold/`.
- Pasteurize emits Cook commands without either flag at `skills/pasteurize/SKILL.md:270-290`. Scoped searches found neither flag in `skills/pasteurize/`.
- Press uses the shared handoff policy at `skills/press/SKILL.md:145-153`. That policy requires both flags.
- Cure consumes `--open-pr` and emits `/plate [--hard]` at `skills/cure/SKILL.md:196-204`.
- Plate accepts `--hard` at `skills/plate/SKILL.md:45-46`. It selects publication mode from the request at `skills/plate/SKILL.md:27-43`.
- Plate has no documented `--open-pr` input. A scoped search found no `--open-pr` in `skills/plate/`.
- Plate defines route and transaction failures at `skills/plate/SKILL.md:109-123`. It does not define a failed hard-gate result.
- No Python import crosses this edge. Plate imports only shared and Plate modules at `src/easy_cheese/skills/plate/commands.py:8-22`.
- Cheese emits no file for Plate. It sends publication intent through `handoff_gate.options[].dispatch` at `skills/cheese/references/handoff-gate.md:65-75`.
- Cheese can attach only route context, such as `wiki_hits`, at `skills/cheese/references/handoff-gate.md:113-139`.
- Plate commands expose only `stack-tools` and `validate-publication` at `src/easy_cheese/skills/plate/commands.py:11-34`.
- Plate validates terminal evidence after publication work at `src/easy_cheese/skills/plate/publication.py:59-174`.
- The hard-gate tests check word presence and the Cure endpoint at `tests/python/test_hard_cheese.py:147-166`.
- The resume test checks that flags occur somewhere in three documents at `tests/python/test_wheypoint_skill_contract.py:173-186`.
- Plate tests do not check Cheese dispatch commands at `tests/python/test_plate_contract.py:13-93`.
- The focused test command reported 79 passes. The passes do not protect the broken routes.

## Findings by severity

### Blocker

none

### High

- **Publication flags can vanish before Plate.** Cheese promises both flags. Mold drops `--open-pr`. Pasteurize drops both flags. A debug route can omit the hard gate. A Mold route can omit requested publication. **Fix:** Make Mold and Pasteurize accept each in-scope flag. Put each flag in the exact next dispatch command.
- **The tests pass when propagation is wrong.** The tests check that words exist. They do not check emitted commands for Cheese, Mold, or debug routes. **Fix:** Add a route matrix for `cook`, `mold`, `debug`, and `--continue`. Assert each exact command through Cure and Plate.

### Medium

- **The prose assigns `--open-pr` to two consumers.** Cheese says the flag reaches Plate. Plate does not accept that flag. Cure consumes it and starts Plate. **Fix:** Make Cure the documented `--open-pr` consumer. State that Cure sends publication intent to Plate.
- **Plate does not define the hard-gate failure mode.** Cheese requires the gate before publication. Plate only defines the active case. **Fix:** State that a failed hard gate halts publication. Map this result to Plate terminal validation.

### Low

none

## STE100 status

not compliant

- `skills/cheese/SKILL.md:120-121` has sentences longer than the allowed limits.
- `skills/plate/SKILL.md:23,53` uses passive voice or combines read and edit instructions.
- This note complies with STE100.
