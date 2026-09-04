# Mold to Hard-cheese edge review

## State

`broken`

Mold does not pass `--hard` on every route to Cook. This defect can bypass the requested final gate.

## Evidence

### Producer

- `skills/mold/SKILL.md:121-125` correctly assigns gate execution to Plate.
- `skills/mold/SKILL.md:131` passes `--hard` only for the `red-required` full-mode route.
- `skills/mold/SKILL.md:47` emits `/cook --auto <spec-path>` without the in-scope flag.
- `skills/mold/references/mini-spec-mode.md:5-8` emits the same incomplete command for every mini-spec disposition.
- `skills/mold/references/handoff-menus.md:3-5` emits incomplete Cook commands for `red-required` and `not-applicable` full-mode routes.
- `src/easy_cheese/skills/mold/commands.py:7-63` contains no hard-cheese import or command.
- `src/easy_cheese/skills/mold/contract_handlers.py:68-85` emits a Mold-to-Cook pointer. It does not emit a hard-cheese call.
- `src/easy_cheese_schemas/contracts.py:678-692` defines every pointer field. The pointer has no field for `--hard`.

The agent dispatch command is therefore the only flag carrier at this edge.

### Consumer

- `skills/hard-cheese/SKILL.md:29-32` requires each upstream skill to pass `--hard`. It makes Plate the only gate runner.
- `skills/hard-cheese/SKILL.md:15-23` defines optional hard-cheese inputs and their defaults. Mold does not override these values.
- `skills/hard-cheese/SKILL.md:62` requires Plate to provide the final inventory and verification rows. Mold does not provide them directly.
- `skills/hard-cheese/references/composition.md:13` requires every upstream skill to pass the flag.
- `skills/hard-cheese/references/composition.md:20-23` defines paths that do not run the gate.
- `skills/hard-cheese/references/composition.md:31-40` defines the non-TTY error and the combined flag behavior.
- `skills/cook/SKILL.md:38-43` accepts the separate `--hard` flag. It cannot recover a flag that Mold omits.
- `skills/plate/SKILL.md:45-46` consumes the flag and runs hard-cheese with the final verified state.

The flag name and presence-only type agree where Mold passes the flag. The default and hard-cheese error modes also agree.

### Tests

- `tests/python/test_hard_cheese.py:150-153` checks only that Mold contains the `--hard` token.
- `tests/python/test_hard_cheese.py:161-166` correctly checks the Plate consumer boundary.
- `tests/python/test_mold_contract_publish.py:85-105` checks the pointer path only. It does not check flag propagation.
- The focused hard-cheese content suite reports 37 passed. It passes while the Mold commands omit the flag.

The tests exercise the consumer boundary. They do not exercise the Mold producer contract.

## Findings by severity

### Blocker

- **Specification and correctness:** Mold omits `--hard` from mini-spec commands and some full-mode commands. Hard-cheese requires every upstream skill to pass the flag. The applied Plate ownership fix remains correct. Mold did not update every producer command. Fix: append `--hard` to every selected Cook command when the flag is present. Apply this rule to all Mold dispositions. Keep Plate as the only gate runner.

### High

- **Assertions:** The propagation test checks token presence instead of the emitted command. It passes when Mold drops the requested gate. Fix: assert exact flag propagation for mini-spec, `red-required`, and `not-applicable` routes. Retain the Plate boundary test as the consumer check.

### Medium

none

### Low

none

## STE100 status

- This note is compliant.
- `skills/mold/SKILL.md` is not compliant. Lines 12, 19, 21, 23-24, and 131 exceed sentence limits. Lines 138-140 combine instructions.
- `skills/hard-cheese/SKILL.md` is not compliant. Lines 30, 32, 47, 127, and 157 use several gate terms. Line 197 combines two instructions.
