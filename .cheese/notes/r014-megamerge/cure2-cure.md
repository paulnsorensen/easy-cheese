# Cure area cure round 2

This note records every finding from the `cure` review, edge, and hub notes.
The area paths are the eight files that the node brief lists.
A finding whose root cause is outside those paths is `deferred: owned by <area>`.

## Findings

| Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| review-cure.md | blocker | The canonical writer deletes the Cure report body. | applied | d664824c | `skills/cure/SKILL.md:157-181` |
| review-cure.md | blocker | The typed Cure path cannot consume each advertised input. | applied | 646630b4 | `skills/cure/SKILL.md:49-57,68-72` |
| review-cure.md | high | The documented writer cannot emit the terminal Cure state. | applied | d664824c | `skills/cure/SKILL.md:171-181` |
| review-cure.md | high | Post-publication write-back leaves tracked changes outside Plate. | applied | 70a099b8 | `skills/cure/SKILL.md:106-107,230,246`; `references/post-pr-writeback.md:6-9` |
| review-cure.md | high | Cure can replace a fresh-context review with a same-context check. | applied | 9a6a83b5 | `skills/cure/SKILL.md:89-93` |
| review-cure.md | low | The selection guide omits the range verb. | applied | ce2e62d8 | `references/selection.md:65` |
| review-cure.md | low | The area uses multiple terms for two workflow concepts. | applied | ce2e62d8, 70a099b8 | `skills/cure/SKILL.md:31,246` |
| review-cure.md | STE100 | Voice, capitalization, and term violations in the area prose. | applied | 8c91ae87, 58ddb14e | `skills/cure/SKILL.md:45,128`; `references/cure-discipline.md:5,7,53` |
| review-cure.md | simplification | Separate normal report repair from the typed path. | applied | 646630b4 | `skills/cure/SKILL.md:49-57` |
| review-cure.md | simplification | Give the writer two complete command examples. | applied | d664824c | `skills/cure/SKILL.md:157-181` |
| review-cure.md | simplification | Remove the `[TBD]` deferred move section. | applied | 70a099b8 | `references/post-pr-writeback.md` |
| review-cure.md | simplification | Replace the model-specific reviewer rule with the resolver. | applied | 9a6a83b5 | `skills/cure/SKILL.md:89-93` |
| review-cure.md | simplification | Keep the command wrappers. | rejected: no change needed | none | `src/easy_cheese/skills/cure/commands.py:66-92` |
| edge-affinage-cure.md | blocker | The typed Cure path cannot consume the Affinage handoff. | applied | 646630b4 | `skills/cure/SKILL.md:49-57` |
| edge-affinage-cure.md | high | The Cure parser drops every Affinage finding. | deferred: owned by shared | none | `src/easy_cheese/shared/findings.py:40-53` |
| edge-affinage-cure.md | high | Cure does not consume `source_report`. | applied | 646630b4 | `skills/cure/SKILL.md:49-51` |
| edge-affinage-cure.md | medium | The Cure result does not preserve the reply contract. | applied | 69eb5e8a | `skills/cure/SKILL.md:196-199` |
| edge-affinage-cure.md | medium | No test exercises this seam. | applied in part | 00eac4c7 | `tests/python/test_cure_contract.py` |
| edge-age-cure.md | blocker | Age cannot satisfy Cure's required input. | applied | 646630b4 | `skills/cure/SKILL.md:49-57` |
| edge-age-cure.md | high | The main Age finding syntax does not match the parser. | deferred: owned by age | none | `skills/age/SKILL.md:157-164` |
| edge-age-cure.md | high | A low-only selection has conflicting states. | deferred: owned by age | none | `skills/age/SKILL.md:183-188` |
| edge-age-cure.md | high | Press findings cannot reach Cure. | deferred: owned by age | none | `skills/age/SKILL.md:92-95` |
| edge-age-cure.md | high | The Age writer can duplicate the handoff preamble. | deferred: owned by age | none | `skills/age/SKILL.md:112-116` |
| edge-age-cure.md | medium | Automatic dispatch can drop `--hard`. | applied | 0dea5b95 | `skills/cure/SKILL.md:99,272`; `references/auto-mode.md:16-18` |
| edge-cheese-cure.md | blocker | The direct route cannot satisfy Cure. | applied | 646630b4 | `skills/cure/SKILL.md:49-57` |
| edge-cheese-cure.md | blocker | The Cure writer can delete the report body. | applied | d664824c | `skills/cure/SKILL.md:157-168` |
| edge-cheese-cure.md | high | Cheese can drop an explicit selection. | deferred: owned by cheese | none | `skills/cheese/SKILL.md:195-201` |
| edge-cheese-cure.md | high | The writer command cannot emit the terminal state. | applied | d664824c | `skills/cure/SKILL.md:171-181` |
| edge-cheese-cure.md | medium | No test exercises the complete seam. | deferred: owned by cheese | none | `skills/cheese/references/classification.md:133-143` |
| edge-cook-cure.md | blocker | Cook omits the Review to Diagnosis transition. | deferred: owned by schemas | none | `src/easy_cheese_schemas/workflow.py:1043-1119` |
| edge-cook-cure.md | blocker | Cure does not give the diagnosis to the repair writer. | deferred: owned by schemas | none | `src/easy_cheese_schemas/workflow.py:331-376` |
| edge-cook-cure.md | blocker | Cure requires bindings for clean curds. | deferred: owned by schemas | none | `src/easy_cheese_schemas/workflow.py:1192-1198` |
| edge-cook-cure.md | blocker | The file handoff cannot transport diagnosis bindings. | deferred: owned by schemas | none | `src/easy_cheese_schemas/_compiled_phase_registry.py:105` |
| edge-cook-cure.md | high | Cook and Cure assign the pass cap to different owners. | applied on this side | none | `skills/cure/SKILL.md:200-201` already assigns the cap to Age |
| edge-cook-cure.md | high | Cook grants publication permission without user input. | deferred: owned by cook | none | `skills/cook/references/auto-mode.md:23-28` |
| edge-cook-cure.md | high | Tests do not exercise the successful seam. | deferred: owned by schemas | none | `tests/schemas/python/test_workflow_thread.py:766-918` |
| edge-cure-age.md | blocker | The declared typed edge has no Age adapter. | deferred: owned by schemas | none | `skills/cure/phase-contract.yaml:5-10` |
| edge-cure-age.md | high | The Cure writer deletes the report body. | applied | d664824c | `skills/cure/SKILL.md:157-168` |
| edge-cure-age.md | high | The scoped Age call loses the pipeline slug. | applied | 0dea5b95 | `skills/cure/SKILL.md:99-102,272` |
| edge-cure-age.md | high | Cure and Age assign the pass cap without state. | deferred: owned by age | none | `skills/age/SKILL.md:214-225` |
| edge-cure-age.md | high | Tests do not exercise the edge from both sides. | applied in part | 00eac4c7 | `tests/python/test_cure_contract.py:147-164` |
| edge-cure-age.md | medium | Cure misstates the `next` field. | applied | d664824c | `skills/cure/SKILL.md:180-181` |
| edge-cure-cheese.md | blocker | Cheese cannot resume a Cure report. | deferred: owned by wheypoint | none | `src/easy_cheese/skills/wheypoint/resolve.py:118-144` |
| edge-cure-cheese.md | blocker | The documented writer removes the Cure report body. | applied | d664824c | `skills/cure/SKILL.md:157-168` |
| edge-cure-cheese.md | blocker | Cheese does not route the canonical status dispositions. | deferred: owned by cheese | none | `skills/cheese/references/continue-resume.md:109-120` |
| edge-cure-cheese.md | high | The writer example cannot emit the terminal state. | applied | d664824c | `skills/cure/SKILL.md:171-181` |
| edge-cure-cheese.md | high | Cure can lose baseline state. | applied | d664824c | `skills/cure/SKILL.md:163-179` |
| edge-cure-cheese.md | high | Cure does not define `artifact:` as the prior report. | applied | d664824c | `skills/cure/SKILL.md:153-155` |
| edge-cure-cheese.md | high | Cure weakens the fresh-context failure mode. | applied | 9a6a83b5 | `skills/cure/SKILL.md:89-93` |
| edge-cure-cheese.md | medium | No test exercises the complete seam. | applied in part | 00eac4c7 | `tests/python/test_cure_contract.py:79-117` |
| edge-cure-hard-cheese.md | high | Cure and hard-cheese define different `ERROR` behavior. | applied | 0dea5b95 | `skills/cure/SKILL.md:259-263` |
| edge-cure-hard-cheese.md | medium | The seam tests protect only route text. | deferred: owned by hard-cheese | none | `tests/python/test_hard_cheese.py:156-166` |
| edge-cure-mold.md | high | Cure requires an untransported `PlannerResult`. | applied | 646630b4 | `skills/cure/SKILL.md:49-57` |
| edge-cure-mold.md | high | Cure cannot consume every domain model shape. | applied | 58ddb14e | `references/domain-model-correction.md:16-27` |
| edge-cure-mold.md | high | Tests do not exercise canonical-term preservation. | deferred: owned by shared | none | `src/easy_cheese/shared/paths.py:555-602` |
| edge-cure-mold.md | medium | The `Avoid` field has two cardinality rules. | applied | 58ddb14e | `references/domain-model-correction.md:41-43` |
| edge-cure-plate.md | high | Cure writes tracked facts after Plate publishes. | applied | 70a099b8 | `references/post-pr-writeback.md:6-9` |
| edge-cure-plate.md | medium | The core dispatch contract lacks paired tests. | applied in part | 00eac4c7 | `tests/python/test_cure_contract.py:153-164` |
| hub-shared.md | blocker | Cure replaces its report with a handoff preamble. | applied | d664824c | `skills/cure/SKILL.md:157-168` |
| hub-shared.md | high | Cure cannot emit its documented terminal state. | applied | d664824c | `skills/cure/SKILL.md:171-181` |
| hub-schemas.md | blocker | Cure cannot apply a selected subset through the typed API. | deferred: owned by schemas | none | `src/easy_cheese_schemas/workflow.py:1192-1210` |
| hub-schemas.md | medium | Cure has no successful direct seam test. | deferred: owned by schemas | none | `tests/schemas/python/test_workflow_thread.py:766-919` |
| hub-build.md | — | The note lists no `cure` row. | rejected: not applicable | none | `.cheese/notes/r014-megamerge/hub-build.md` |

## Notes on two decisions

The review asked for the term `automatic mode` through the area.
The `## Auto mode` heading remains, because `skills/cook/references/auto-mode.md:142` and
`tests/python/test_hard_cheese.py:299-306` anchor on that exact heading.
The running prose now uses `automatic mode`, and the section names stay stable.

The review asked to move knowledge capture before the Plate write gate.
The operation keeps the name `post-PR write-back`, because the review also asked for one term.
The order changed, and the name did not.

## Verification

`bash .milknado/reconcile-gate.sh` returns exit code 0.
The run covers `ruff check`, `just typecheck`, `validate_skills.py`, and 17 area tests.

## Follow-ups

- Accept the Affinage finding grammar in `src/easy_cheese/shared/findings.py`.
- Add a selected-curd input to the typed Cure API in `src/easy_cheese_schemas/workflow.py`.
- Run diagnosis after each non-clean review, and give the confirmed result to the Cure writer.
- Register a versioned Cure input contract that transports the plan and bindings.
- Let Wheypoint resolve an exact registered phase report.
- Route the canonical status dispositions in Cheese.
- Add the hard-gate outcome matrix test in the hard-cheese area.
- Add canonical-term preservation tests over each domain model backend.
