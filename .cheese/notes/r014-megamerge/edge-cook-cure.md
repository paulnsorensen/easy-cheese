# Cook to Cure Edge Review

## State

broken

Cook cannot produce the required diagnosis binding after a failed review.
Cure also does not pass the diagnosis to its repair writer.
The file handoff has no typed transport for the binding.

## Evidence

| Surface | Cook producer | Cure consumer | State |
| --- | --- | --- | --- |
| Public API | Cook directs the host to call `bind_diagnosis` and `cure` (`skills/cook/references/fan-pathway.md:79-100`). | Cure uses the same names (`skills/cure/SKILL.md:64-75`). The package exports them (`src/easy_cheese_schemas/__init__.py:255-264,390-410`). | ok |
| Binding shape | Cook requires an exact plan and curd binding (`skills/cook/references/fan-pathway.md:87-98`). | Cure accepts a mapping or tuple (`src/easy_cheese_schemas/workflow.py:126-143,1142-1211`). | broken |
| Result shape | Cook expects and stores normalized `CurdResult` values (`skills/cook/references/fan-pathway.md:79-100,293-324`). | Cure returns `ExecutionResults` with `CurdResult` values (`src/easy_cheese_schemas/workflow.py:77,1214-1329`). | ok |
| File handoff | Cook writes one `artifact` field with a `curd-result` route (`skills/cook/SKILL.md:131-165`). | Cure requires a plan and diagnosis bindings (`skills/cure/SKILL.md:49-75,135-173`). | broken |
| Commands and imports | Cook exposes local and shared commands (`src/easy_cheese/skills/cook/commands.py:112-186,189-260`). | Cure exposes shared commands only (`src/easy_cheese/skills/cure/commands.py:7-96`). No direct cross-area import exists. | ok |
| Automatic flags | Cook defines `--open-pr` as separate permission (`skills/cook/SKILL.md:38-43`). | Cure forwards the flag only when it is in scope (`skills/cure/SKILL.md:236-245`). | broken |
| Tests | Cook tests require contract names in prose (`tests/python/test_ultracook_skills.py:1279-1297`). | Cure tests cover names and invalid bindings (`tests/python/test_ultracook_skills.py:1440-1461`; `tests/schemas/python/test_workflow_thread.py:766-918`). | untested |

`CureDiagnosisBinding` has three required fields and no defaults.
The fields are `source_plan_ref`, `source_curd_ref`, and `diagnosis` (`src/easy_cheese_schemas/workflow.py:126-143`).
`bind_diagnosis` creates both source references from canonical plan data (`src/easy_cheese_schemas/workflow.py:427-442`).
Cure rejects wrong collection types, wrong keys, duplicates, stale references, and unconfirmed diagnoses (`src/easy_cheese_schemas/workflow.py:1142-1211`).
These names, types, and error modes agree with both skill files.

`CurdResult` requires source references, complete criterion coverage, disposition, deliverables, unresolved work, and runtime references.
The result contract also derives its disposition (`src/easy_cheese_schemas/contracts.py:1692-1764`).
Cook and Cure agree on this result shape.

## Findings

### Blocker

- **Cook omits the Review to Diagnosis transition.** Cook promises this transition at `skills/cook/references/fan-pathway.md:87-92`. The runtime reviews passing writer output at `src/easy_cheese_schemas/workflow.py:1043-1083`. It diagnoses only failed writer output at `src/easy_cheese_schemas/workflow.py:1083-1119`. A blocked review returns a `ReviewResult` without a `DiagnosisResult`. Cure cannot receive its required confirmed binding. **Fix:** Run diagnosis after each non-clean review. Normalize its result. Bind only a confirmed result to the reviewed curd.

- **Cure does not give the diagnosis to the repair writer.** Cure validates the binding at `src/easy_cheese_schemas/workflow.py:1180-1211`. It adds only `diagnosis_id` to result provenance at `src/easy_cheese_schemas/workflow.py:1252-1258`. The writer context has no diagnosis field (`src/easy_cheese_schemas/workflow.py:331-376`). The probe confirmed that the context omitted `diagnosis`. **Fix:** Add the confirmed `DiagnosisResult` to the Cure writer context. Keep this field absent from Cook writer contexts.

- **Cure requires bindings for clean curds.** Cook routes one failed curd through Cure (`skills/cook/references/fan-pathway.md:220-246`). Cure prose requests one binding for each selected curd (`skills/cure/SKILL.md:64-75`). Runtime validation requires bindings for every plan curd (`src/easy_cheese_schemas/workflow.py:1192-1198`). A clean sibling has no confirmed diagnosis. The two-curd probe rejected one valid selected binding before dispatch. **Fix:** Accept a non-empty binding subset. Execute only those bound curds. Reject bindings for curds outside the validated plan.

- **The file handoff cannot transport diagnosis bindings.** Cook emits only the standard preamble and one artifact path (`skills/cook/SKILL.md:131-165`). The writer has no plan or diagnosis field (`src/easy_cheese/shared/write_handoff_artifact.py:200-239`). The Age-to-Cure route sends only `curd-plan` (`src/easy_cheese_schemas/_compiled_phase_registry.py:105`). `CureDiagnosisBinding` has no registered schema. **Fix:** Add a versioned Cure input contract. Include the plan reference and binding collection. Register its schema and persist one canonical artifact.

### High

- **Cook and Cure assign the pass cap to different owners.** Cook assigns the cap to its fixed loop (`skills/cook/references/auto-mode.md:59-81`). Cure assigns the cap to Age (`skills/cure/SKILL.md:172-173,236-245`). One chain can stop at the wrong pass. **Fix:** Assign the cap to Age in both files. Pass the completed count with each Age dispatch.

- **Cook grants publication permission without user input.** Cook defines `--open-pr` as separate permission (`skills/cook/SKILL.md:38-43`). Its automatic reference always appends the flag (`skills/cook/references/auto-mode.md:23-28`). Cure correctly forwards the flag only when it is in scope (`skills/cure/SKILL.md:236-245`). **Fix:** Append `--open-pr` only when the user supplied it.

- **Tests do not exercise the successful seam from both sides.** The runtime tests reject missing, unconfirmed, and unsupported inputs (`tests/schemas/python/test_workflow_thread.py:766-918`). The skill tests only search for contract names (`tests/python/test_ultracook_skills.py:1286-1291,1443-1456`). No test passes a confirmed diagnosis through Cure and inspects the repaired result. **Fix:** Add one complete Cook to Cure test. Add tests for diagnosis delivery, selected curds, and artifact transport.

### Medium

none

### Low

none

## Verification

The focused suite passed with 16 tests and 142 deselections.
The command used the repository test dependencies and both seam test files.
`uv run --no-project --with-requirements requirements/runtime.txt --with pip==26.2.1 --with pytest==9.0.3 --with pyyaml==6.0.2 python3 -m pytest -q tests/schemas/python/test_workflow_thread.py tests/python/test_ultracook_skills.py -k 'cure or CookTypedTopology or CureCanonicalPathway'` passed.

A blocked-review probe recorded `writer` and `review` events only.
It returned a blocked `ReviewResult` and did not call diagnosis.

A confirmed Cure probe returned one repaired `CurdResult`.
Its writer context omitted `diagnosis` and kept only the identifier in `runtime_refs`.

A two-curd probe supplied one confirmed binding.
Cure rejected it with `missing=['workflow-request/plan/curd/2']` before dispatch.

## Contract changes not followed

- Cook adds a typed diagnosis binding. Cure retains only its identifier during writer dispatch.
- Cure assigns the pass cap to Age. Cook retains fixed-loop ownership.
- Cook automatic mode grants `--open-pr`. Cure retains explicit permission scope.
- Cure prose selects curds. Runtime validation retains whole-plan binding coverage.

## STE100 status

The note is compliant.

- `skills/cook/SKILL.md:63,250` combines two instructions in each sentence.
- `skills/cook/SKILL.md:241` uses the passive voice.
- `skills/cure/SKILL.md:31,236` uses two terms for automatic mode.
- `skills/cure/SKILL.md:45` does not start with a capital letter.
- `skills/cure/SKILL.md:116` uses the passive voice.
- `skills/cure/SKILL.md:205,221-225,246` uses inconsistent post-PR write-back terms.

## Follow-ups

- Fix all four blocker findings before integration.
- Add the complete seam tests before integration.
- Align pass ownership and publication permission in both skills.
- Correct the listed STE100 violations in both skill files.
