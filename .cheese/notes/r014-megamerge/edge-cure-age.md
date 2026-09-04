# Cure to Age edge review

## State

broken

The route can select Age, but the typed payload and scoped review contract do not connect.
Tests check isolated parts, but no test executes the complete edge.

## Evidence

### Calls and imports

- Cure requests `/age --scope <touched-path>` after repair (`skills/cure/SKILL.md:94-99,175-180,209-219`).
- Automatic Cure requests `/age --scope <touched-paths> --auto` (`skills/cure/SKILL.md:236-245`; `skills/cure/references/auto-mode.md:6-20`).
- The Cook fan route writes `next: age` and lets the orchestrator dispatch Age (`skills/cure/references/auto-mode.md:46-62`).
- Cure has no direct Age runtime import (`src/easy_cheese/skills/cure/commands.py:1-95`).
- Its bundle imports the shared handoff writer and findings parser (`src/easy_cheese/skills/cure/commands.py:17-35`).
- Cure also applies the Age voice rules (`skills/cure/SKILL.md:265-267`).
- The shared phase router selects Age after Cure (`src/easy_cheese/shared/fanout/phase_decision.py:100-116,143-145,261-270`).

### Emitted file and fields

- Cure writes `.cheese/cure/<slug>.md` with `status`, `next`, `artifact`, `baseline`, and orientation (`skills/cure/SKILL.md:135-149`).
- The shown writer command emits `next: age` with the `curd-result` schema (`skills/cure/SKILL.md:151-159`).
- The command omits `--body-file`, `--baseline`, and `--durable-flags` (`skills/cure/SKILL.md:151-159`).
- The shared writer replaces the target with the preamble when no body exists (`src/easy_cheese/shared/write_handoff_artifact.py:106-109,164-190`).
- Cure declares a `CurdResult` output, and Age declares the same input (`skills/cure/phase-contract.yaml:5-10`; `skills/age/phase-contract.yaml:5-10`).
- The Cure API returns one result for each curd (`src/easy_cheese_schemas/workflow.py:76-78,1214-1277,1305-1329`).
- Age accepts a diff, range, one scoped path, or a Press slug (`skills/age/SKILL.md:17-35`).
- Age reads Press and Cook state, but it does not read a Cure handoff (`skills/age/SKILL.md:92-100`).
- The Age report template expects a prior Cure path in `artifact` (`skills/age/references/report-example.md:34-54`).
- The Age writer command instead emits an empty `artifact` (`skills/age/SKILL.md:112-116`).

### Defaults and errors

- Cure defaults to `next: age` for automatic and interactive repair (`skills/cure/SKILL.md:164-173`).
- Cure permits `next: done` only after an explicit interactive choice (`skills/cure/SKILL.md:168-171`).
- The writer rejects an undeclared phase route or payload schema before it writes (`src/easy_cheese/shared/write_handoff_artifact.py:47-58,125-173`).
- Age emits `next: cure` for medium-or-higher findings and `next: done` otherwise (`skills/age/SKILL.md:109-117,183-188`).
- Cure assigns the two-pass cap to Age (`skills/cure/SKILL.md:172-173,236-245`).
- Age has no pass-count input, but its automatic flow tries to count completed Cure passes (`skills/age/SKILL.md:17-22,214-225`).
- The Cook fan rule instead says Age does not count passes (`skills/age/references/handoff-detail.md:90-109`).

### Tests

- The focused test command passed 133 tests.
- Phase tests prove only that Cure routes to Age (`tests/fanout/python/test_phase_decision.py:38-57`; `tests/fanout/python/test_phase_decision_tables.py:82-120`).
- Registry tests prove schema-name compatibility, but they do not execute Cure to Age (`tests/schemas/python/test_phase_contracts.py:124-151,498-532`).
- The Cure handoff test checks only path and field text (`tests/python/test_ultracook_skills.py:242-252`).
- The scoped-chain test checks one literal command string (`tests/python/test_ultracook_skills.py:796-818`).
- No test writes a Cure result and then starts Age with its state.

## Findings by severity

### Blocker

- **[correctness:blocker] The declared typed edge has no Age adapter.** Cure declares `CurdResult`, but it produces a result tuple. Age documents only review targets and no result consumer. **Fix:** Use `ReviewRequest` for this edge. Put touched paths in `coverage_targets`, and bind Cure results as evidence. Add one Age adapter.

### High

- **[correctness:high] The Cure writer deletes the report body before review.** The command writes the existing target without `--body-file`. This removes `Applied`, `Checks`, and `Re-review`. **Fix:** Build one body-only file. Let the writer create the final Cure report once. Preserve baseline and durable flags.
- **[correctness:high] The scoped Age call loses the pipeline slug.** Cure sends plural touched paths, but Age accepts one path and needs a slug. No separator or slug rule exists. **Fix:** Accept repeated `--scope` values. Require the current slug on every Cure dispatch.
- **[spec:high] Cure and Age assign the pass cap without transferable state.** Cure delegates the cap to Age. Age receives no counter, and its Cook rule rejects Age ownership. **Fix:** Let the top-level Cook phase router own the cap. Remove pass counting from Cure and Age.
- **[assertions:high] Tests do not exercise the edge from both sides.** Current tests verify routing, declarations, or prose independently. **Fix:** Write a Cure handoff, run the Age adapter, and verify both terminal outcomes. Cover invalid payloads, multiple paths, flags, and body preservation.

### Medium

- **[spec:medium] Cure misstates the `next` field.** Cure says `phase` and `next` control storage routing. The writer uses only `phase` for storage. **Fix:** Say that `next` declares and validates the following phase (`skills/cure/SKILL.md:161`; `src/easy_cheese/shared/write_handoff_artifact.py:20-24`).

### Low

none

## STE100 status

not compliant

- `skills/age/SKILL.md:128,208,218-223` has long or combined instructions and an undefined pass-count input.
- `skills/cure/SKILL.md:31,45,116,205,221,236,246` has inconsistent terms, capitalization, or voice.
- This note uses short active sentences and one term for each meaning.

## Follow-ups

- Add one typed Cure-to-Age `ReviewRequest` adapter.
- Preserve the Cure report body and all handoff fields.
- Define the slug and repeated-scope syntax for Cure reviews.
- Keep the Cure pass cap in the top-level phase router.
- Add one end-to-end Cure-to-Age contract test.
