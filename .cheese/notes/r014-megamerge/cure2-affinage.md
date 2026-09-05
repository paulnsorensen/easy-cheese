# Cure round 2 — affinage

This note records every finding from the affinage review notes.
Each row gives the source note, the severity, the state, the commit, and the evidence.

## Area paths

The node owns these eight paths.

- `skills/affinage/SKILL.md`
- `skills/affinage/references/auto-mode.md`
- `skills/affinage/references/commands.md`
- `skills/affinage/references/flow-details.md`
- `skills/affinage/references/handoff-templates.md`
- `skills/affinage/references/merge-conflict.md`
- `skills/affinage/references/report-template.md`
- `src/easy_cheese/skills/affinage/commands.py`

The node also adds `tests/python/test_affinage_contract.py`.
`src/easy_cheese/skills/affinage/pr_status.py` and `post_reply.py` are outside these paths.
The node defers each finding whose fix belongs to those two files.

## Findings

| # | Source note | Severity | Finding | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | review-affinage.md | blocker | Conflict resolution cannot reach publication. | applied | `0618f58d` | `skills/affinage/references/merge-conflict.md:12-20`; `skills/affinage/SKILL.md:108-116` |
| 2 | review-affinage.md | blocker | The reply gate cannot approve Cure replies. | applied | `11d86ff4`, `7fbc587c` | `skills/affinage/references/handoff-templates.md:30-46`; `skills/affinage/SKILL.md:99-107` |
| 3 | review-affinage.md | high | Affinage contradicts the shared portability rules. | applied | `fe6c68b4`, `8b932f03` | `skills/affinage/SKILL.md:62-68` |
| 4 | review-affinage.md, hub-shared.md | high | The halt instruction omits the required `status:` key. | applied | `4404d5a2` | `skills/affinage/SKILL.md:189` |
| 5 | review-affinage.md | high | The report template emits an invalid location value. | applied | `12c0ddf7` | `skills/affinage/references/report-template.md:40-43,78-79` |
| 6 | review-affinage.md | high | Review-body replies are not idempotent. | deferred: owned by the Affinage runtime module `post_reply.py`, which is outside the eight area paths | none | `src/easy_cheese/skills/affinage/post_reply.py:134-136` |
| 7 | review-affinage.md | medium | Four prose files violate the STE100 rules. | applied | `3e503090` | `skills/affinage/SKILL.md:44-46,54-57,87-88`; `references/flow-details.md:23,56-58,75-76`; `references/handoff-templates.md:21-24`; `references/auto-mode.md:11` |
| 8 | review-affinage.md | low | One output instruction assigns Affinage sections to Age. | applied | `3e503090` | `skills/affinage/SKILL.md:174-175` |
| 9 | edge-affinage-cure.md | blocker | The typed Cure path cannot consume the Affinage handoff. | deferred: owned by cure and schemas; the fix adds a report repair path to `skills/cure/SKILL.md` and `src/easy_cheese_schemas/workflow.py` | none | `skills/cure/SKILL.md:49-75`; `src/easy_cheese_schemas/workflow.py:1180-1210` |
| 10 | edge-affinage-cure.md | high | The Cure parser silently drops every Affinage finding. | applied on this side | `c024ea79` | `skills/affinage/references/report-template.md:7-12,26-43`; `tests/python/test_affinage_contract.py:121-136` |
| 11 | edge-affinage-cure.md | high | Cure does not consume the producer's `source_report` field. | deferred: owned by cure; the fix loads `handoff_context.source_report` in `skills/cure/SKILL.md` | none | `skills/cure/SKILL.md:14-20`; `skills/cure/references/selection.md:23-45` |
| 12 | edge-affinage-cure.md | medium | The Cure result does not preserve the reply contract. | deferred: owned by cure; the fix binds the Cure slug and headings in `skills/cure/SKILL.md` | none | `skills/cure/SKILL.md:135-180` |
| 13 | edge-affinage-cure.md | medium | Tests do not exercise this seam from either side. | applied on this side | `109a385a` | `tests/python/test_affinage_contract.py:118-136` |
| 14 | edge-affinage-hard-cheese.md | high | The Affinage hard-gate edge has no regression test. | applied | `109a385a` | `tests/python/test_affinage_contract.py:139-160` |
| 15 | edge-affinage-pasteurize.md | blocker | The reproduction command can confirm the wrong claim. | deferred: owned by pasteurize; the fix adds output matchers to `repro_rerun.py` | none | `src/easy_cheese/skills/pasteurize/repro_rerun.py:42-56` |
| 16 | edge-affinage-pasteurize.md | high | Pasteurize cannot return an investigation verdict to Affinage. | deferred: owned by pasteurize; the fix adds a typed investigation request and result to `skills/pasteurize/SKILL.md` | none | `skills/pasteurize/SKILL.md:245-268` |
| 17 | edge-affinage-pasteurize.md | medium | Tests do not exercise the Pasteurize seam from either side. | deferred: the producer test needs the Pasteurize request contract from finding 16 | none | `skills/affinage/references/flow-details.md:86-91` |
| 18 | edge-cheese-affinage.md | high | Cheese emits a pull request form that Affinage does not accept. | applied on this side | `602b862f` | `skills/affinage/SKILL.md:36-40,73-75`; `tests/python/test_affinage_contract.py:166-172` |
| 19 | edge-cheese-affinage.md | high | Affinage cannot use the canonical durable handback path. | deferred: owned by schemas; the fix registers an Affinage phase contract in `_compiled_phase_registry.py` | none | `src/easy_cheese_schemas/_compiled_phase_registry.py:5-103` |
| 20 | edge-cheese-affinage.md | medium | The `artifact` field has two meanings on this edge. | deferred: owned by cheese; the fix adds a typed `pr_ref` field to `continue-resume.md` | none | `skills/cheese/references/continue-resume.md:104-108` |
| 21 | edge-cheese-affinage.md | medium | Explicit resume auto mode lacks the required Affinage stake. | applied | `602b862f` | `skills/affinage/SKILL.md:44-47`; `tests/python/test_affinage_contract.py:175-177` |
| 22 | edge-cheese-affinage.md | medium | Tests do not exercise the Cheese to Affinage seam. | applied on this side | `602b862f`, `109a385a` | `tests/python/test_affinage_contract.py:166-177` |
| 23 | hub-shared.md | medium | Generated JSON commands treat `--help` as a file path. | deferred: owned by shared; the fix adds help handling to `json_command` | none | `src/easy_cheese/shared/bundle_commands.py` |
| 24 | hub-schemas.md | blocker | Cure cannot apply a selected subset through its typed API. | deferred: owned by schemas and cure | none | `src/easy_cheese_schemas/workflow.py:1192-1210` |
| 25 | hub-schemas.md | high | Cheese does not consume the full phase registry. | deferred: owned by cheese and schemas | none | `skills/cheese/references/continue-resume.md:98-122` |
| 26 | hub-build.md | — | The note has no Affinage row. | not applicable | none | `.cheese/notes/r014-megamerge/hub-build.md` |

## Simplifications

The review lists five simplifications.
Four already hold at HEAD.

- Auto-mode decisions stay in `SKILL.md`. The process stays in `references/auto-mode.md`. Applied at `skills/affinage/SKILL.md:218-233`.
- Conflict order and ownership now live only in `references/merge-conflict.md`. `SKILL.md` links to that file. Applied in `0618f58d`.
- `fresh review` is the only term for the extra Age pass. Applied in `3e503090`.
- The four command wrappers stay. The static command manifest needs their decorators. No change at `src/easy_cheese/skills/affinage/commands.py:14-55`.
- No `_with_summary` helper remains. `derive_command` owns the command summaries. No change.

## Rejected findings

- Finding 3 asks the node to remove the phrase "slash commands are host renderings, not the control model".
  The node rejects that part of the fix.
  `tests/python/test_docs_emphasis_guard.py:78-97` requires that exact phrase in every workflow skill.
  That test belongs to the build area.
  The node keeps the phrase and removes only the `${CLAUDE_SKILL_DIR}` fallback.
  Commit `8b932f03` records this choice.

## Disagreements

- `review-affinage.md` marks the Affinage to Cure edge `ok`. `edge-affinage-cure.md` marks it `broken`.
  The node keeps the typed schema contract.
  The shared parser in `src/easy_cheese/shared/findings.py:40-53` defines the finding grammar.
  The node changed `report-template.md` to match that parser.
  The provenance tag moved from the bullet to an indented `source:` line.
- `review-affinage.md` calls the portability phrase a false quotation.
  The build gate requires that phrase.
  The node keeps the phrase, as recorded above.

## Verification

- `tests/python/test_affinage_contract.py`: 20 tests pass.
- `tests/python`: 1593 pass and 23 fail.
- The same 23 tests fail at the base commit `c7a75d48`.
- Those failures are stale bundle archives and unrelated schema migration checks.
- The reconcile gate `.milknado/reconcile-gate.sh` exits zero.

## STE100 status

compliant

All eight area files use active voice, one instruction per sentence, and one term for each meaning.
This note uses the same rules.

## Follow-ups

- Add a report repair path to Cure for Affinage handoffs (finding 9).
- Load `handoff_context.source_report` in Cure (finding 11).
- Bind the Cure result slug and headings to the Affinage reply contract (finding 12).
- Give `post_reply` a stable review identifier for PR-level replies (finding 6).
- Add expected exit and output matchers to the Pasteurize rerun command (finding 15).
- Add a typed Pasteurize investigation request and verdict (findings 16 and 17).
- Register an Affinage phase contract, or narrow the shared writer claim (findings 19 and 25).
- Add a typed `pr_ref` field to the Cheese resume route (finding 20).
- Add `--help` handling to the shared `json_command` helper (finding 23).
- Add a selected-curd input to the typed Cure API (finding 24).
- Rebuild the skill bundles at the integration barrier.
