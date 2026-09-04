# Cheese to Pasteurize edge review

## State

`broken`

Cheese selects Pasteurize when a reported failure has no confirmed cause.
The default route passes `--auto`, which Pasteurize accepts.
The forward flags, context, and handoff contracts do not agree.

## Evidence

| Contract | Cheese evidence | Pasteurize evidence | State |
| --- | --- | --- | --- |
| Intent | `skills/cheese/references/classification.md:103-118` selects Pasteurize for symptom-driven work without a confirmed cause. | `skills/pasteurize/SKILL.md:22-71` requires a reproduction loop before diagnosis. | `ok` |
| Dispatch command | `skills/cheese/SKILL.md:194` emits `/pasteurize --auto <input>` by default. | `skills/pasteurize/SKILL.md:285-290` defines `--auto` and starts Cook after cleanup. | `ok` |
| Other commands and imports | Cheese does not call a Pasteurize Python module or bundle command. | `src/easy_cheese/skills/pasteurize/commands.py:7-44` exposes only three internal bundle commands. | `ok` |
| Dispatch context | `skills/cheese/SKILL.md:50-55` emits `handoff_context.wiki_hits` with `page`, `line`, and `why`. | `skills/pasteurize/SKILL.md:9-22` defines no input packet or `wiki_hits` behavior. | `broken` |
| Forward flags | `skills/cheese/SKILL.md:25-30` promises `--open-pr` and `--hard` propagation. | `skills/pasteurize/SKILL.md:178-180,241,272-290` forwards only `--auto`. | `broken` |
| Emitted artifact | `skills/cheese/references/handback-contract.md:15-32,67-88` requires one canonical preamble. | `skills/pasteurize/SKILL.md:245-264` inserts five unsupported keyed lines and changes `artifact:` semantics. | `broken` |
| Error modes | `skills/cheese/references/handback-contract.md:34-65,108-122` makes `halt` stop and ignore `next:`. | `skills/pasteurize/SKILL.md:263,292-305` tells a halted run to route to Mold. | `broken` |
| Runtime transition | `src/easy_cheese/shared/write_handoff_artifact.py:47-58,125-153` validates every phase before writing. | `src/easy_cheese_schemas/_compiled_phase_registry.py:5-103` has no Pasteurize phase. | `broken` |
| Tests | `tests/python/test_cheese_routing_receipt.py:1-146` does not test the debug route. | `tests/pasteurize/python/test_repro_rerun.py:23-158` and `tests/pasteurize/python/test_debug_tag_sweep.py:1-213` test helper commands only. | `untested` |

The writer probe used `--phase pasteurize --next cook`.
It exited with status 3 and reported `unknown source phase 'pasteurize'`.
The parser probe used the documented Pasteurize minimum handoff.
It parsed `cause: cache race` as the orientation.

## Findings

### Blocker

none

### High

- Cheese promises `--open-pr` and `--hard` propagation, but Pasteurize drops both flags. A debug route can omit publication and the final hard gate. Fix: Define these flags in Pasteurize. Forward them to every Cook option.
- Pasteurize cannot write its handoff through the canonical writer. The phase registry omits Pasteurize, and the documented preamble does not match the parser. Fix: Add a Pasteurize phase declaration. Use the diagnosis contracts. Move `cause`, `loop`, `seam`, `fix`, and `follow_up` into the report body. Keep `artifact:` as the prior report pointer.
- Pasteurize uses a stop status for outcomes that it tells the orchestrator to route. The canonical router ignores `next:` after `halt`. Fix: Use `needs-context` when reproduction access is missing. Use a proceed status for an automatic Mold route, or remove the route instruction.
- Tests do not exercise this seam from either side. The hard-flag test also omits Pasteurize at `tests/python/test_hard_cheese.py:143-153`. Fix: Test debug classification, flag preservation, context input, transition validation, and handoff round trips.

### Medium

- Cheese emits `handoff_context.wiki_hits`, but Pasteurize defines no consumer behavior. The diagnosis can silently ignore prior decisions. Fix: Add an Inputs section to Pasteurize. Define `<input>`, accepted flags, and optional `wiki_hits`. Use the hits before Phase 1.

### Low

none

## STE100 status

`noncompliant`

- `skills/cheese/SKILL.md:41` puts four instructions in one sentence.
- `skills/cheese/SKILL.md:61` puts three instructions in one sentence.
- `skills/pasteurize/SKILL.md:39` puts four instructions in one sentence.
- `skills/pasteurize/SKILL.md:142` puts two instructions in one sentence.
- `skills/pasteurize/SKILL.md:204` uses the passive voice.

## Follow-ups

- Repair the Pasteurize phase declaration and canonical handoff.
- Preserve `--open-pr` and `--hard` across the Pasteurize to Cook transition.
- Define and test the Cheese dispatch packet that Pasteurize consumes.
- Repair the listed STE100 violations in both skill files.
