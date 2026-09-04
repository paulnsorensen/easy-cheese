# Cheese to Cure Edge Review

## State

broken

Cheese can dispatch Cure, but the direct input cannot satisfy the required typed Cure path.
Cheese can also lose an explicit finding selection.

## Evidence

| Surface | Cheese side | Cure side | State |
| --- | --- | --- | --- |
| Dispatch command | Cheese dispatches `/cure <slug>` for a fresh Age report (`skills/cheese/references/classification.md:133-143`). | Cure accepts `/cure <slug>` and reads `.cheese/age/<slug>.md` (`skills/cure/SKILL.md:14-25`). | ok |
| Pre-dispatch check | Cheese checks only for a finding list or Age report (`skills/cheese/references/coherence-check.md:28-33`). | Cure requires `PlannerResult`, `CurdPlan`, a valid digest, and confirmed diagnosis bindings (`skills/cure/SKILL.md:49-75`). | broken |
| Typed runtime | Cheese passes a slug and optional wiki context (`skills/cheese/SKILL.md:50-60,195-201`). | `cure` requires `CurdPlan` and `CureDiagnosisBindings` (`src/easy_cheese_schemas/workflow.py:1180-1211,1305-1329`). | broken |
| Finding selection | Cheese defines `wiki_hits` for its target context (`skills/cheese/references/handoff-gate.md:113-138`). | Cure requires `selection` and `resolved_ids` for a locked selection (`skills/cure/references/selection.md:21-41`). | broken |
| Default selection | Cheese does not define a selection default for its direct Cure route (`skills/cheese/SKILL.md:195-201`). | Cure uses `all-medium, cheap` when no locked selection exists (`skills/cure/references/selection.md:3-18`). | broken |
| Flags | Cheese carries `--open-pr` and `--hard` through the implementation chain (`skills/cheese/SKILL.md:23-30`). | Cure accepts both flags and passes `--hard` to Plate (`skills/cure/SKILL.md:27-38`). | ok |
| Runtime imports | Cheese remains a read-only router and uses dispatch only (`skills/cheese/SKILL.md:64-73`). | The Cure command surface imports shared helpers only (`src/easy_cheese/skills/cure/commands.py:7-63`). | ok |
| Cure report fields | Cheese accepts `status`, `next`, `artifact`, orientation, and optional keyed lines (`skills/cheese/references/handback-contract.md:15-32,67-91`). | Cure emits those fields in `.cheese/cure/<slug>.md` (`skills/cure/SKILL.md:135-170`). | broken |
| Terminal state | Cheese stops on terminal `next: done` (`skills/cheese/references/continue-resume.md:160-181`). | Cure documents `done`, but its shown writer command always emits `age` (`skills/cure/SKILL.md:151-170`). | broken |
| Error modes | Cheese stops for a missing report or invalid handoff (`skills/cheese/references/coherence-check.md:9-13`; `skills/cheese/references/continue-resume.md:38-59`). | Cure stops before dispatch for invalid plans or bindings (`skills/cure/SKILL.md:49-75`). | ok |
| Tests | Cheese tests cover regrounding and the generic receipt (`tests/python/test_cheese_reground.py:49-135`; `tests/python/test_cheese_routing_receipt.py:47-145`). | Cure tests reject missing or invalid bindings (`tests/schemas/python/test_workflow_thread.py:820-918`). | untested |

Cheese emits no file and imports no Cure module.
It emits one host dispatch command and optional `handoff_context.wiki_hits`.
Cure emits `.cheese/cure/<slug>.md`, which Cheese can read during a later resume.

## Findings by severity

### Blocker

- **The direct route cannot satisfy Cure.** Cheese dispatches an Age slug after it confirms only that findings exist (`skills/cheese/references/coherence-check.md:28-33`). Cure then requires a typed plan and complete confirmed bindings (`skills/cure/SKILL.md:49-75`; `src/easy_cheese_schemas/workflow.py:1180-1211`). The integrated Cure contract added these typed requirements. Cheese still sends only the slug and optional wiki context. **Fix:** Define a normal report repair path in Cure. Use the typed path only when the handoff supplies all typed inputs.
- **The Cure writer can delete the report body.** Cheese defines a durable report as a preamble plus body (`skills/cheese/references/handback-contract.md:67-88`). Cure first writes the report, then shows a writer command without `--body-file` (`skills/cure/SKILL.md:97-99,151-159`). The writer replaces the target with only the preamble when the body is absent (`src/easy_cheese/shared/write_handoff_artifact.py:106-109,164-175`). **Fix:** Write a body-only file. Pass it with `--body-file` in the Cure command.

### High

- **Cheese can drop an explicit selection.** Cheese sends only `/cure <slug>` and optional `wiki_hits` on its direct route (`skills/cheese/SKILL.md:195-201`; `skills/cheese/references/handoff-gate.md:127-138`). Cure accepts a locked selection only through `selection` and `resolved_ids` (`skills/cure/references/selection.md:21-41`). Cure otherwise selects `all-medium, cheap` (`skills/cure/references/selection.md:3-18`). This default can change the requested repair scope. **Fix:** Put the selection verb and expanded identifiers in the Cheese dispatch packet.
- **The shown writer command cannot emit the documented terminal state.** Cheese correctly handles `next: done` (`skills/cheese/references/continue-resume.md:160-181`). Cure permits that state, but its command always uses `--next age` and a result schema (`skills/cure/SKILL.md:151-170`). **Fix:** Show separate commands for `age` and `done`. Omit the payload schema for the terminal command.

### Medium

- **No test exercises the complete seam.** The checked `tests/**/*` scope has no assertion for `age-then-cure`, `target=/cure`, or `resolved_ids`. Cheese tests cover generic router behavior, while Cure tests start at typed validation. **Fix:** Add one contract test that starts with Cheese classification and reaches Cure selection. Add cases for missing typed inputs and terminal output.

### Low

none

## STE100 status

not compliant

- `skills/cheese/SKILL.md:136` has a procedural sentence longer than 20 words.
- `skills/cure/SKILL.md:45` starts a sentence with a lowercase word.
- `skills/cure/SKILL.md:31,236` uses two terms for automatic mode.
- `skills/cure/SKILL.md:205,221,246` uses two terms for post-PR write-back.
- This review note complies with the required writing rules.
