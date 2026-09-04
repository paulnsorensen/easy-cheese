# Age to Cure Edge Review

## State

broken

Age cannot supply Cure's required typed input. The report contract also has inconsistent states and formats.

## Evidence

### Dispatch and context

- Age dispatches `/cure <slug>` only for a nonempty selection at `skills/age/references/handoff-detail.md:57-85`.
- Age emits `source_skill`, `source_report`, `selection`, and `resolved_ids` at `skills/age/references/handoff-detail.md:71-84`.
- Cure requires the same fields at `skills/cure/references/selection.md:21-41`.
- The shown field names and types agree. `selection` is text, and `resolved_ids` is an integer list.
- Cure calculates `all-medium, cheap` when locked context is absent at `skills/cure/references/selection.md:3-15`.
- Age does not import a Cure runtime module. Both bundles import the shared findings command.
- The imports are at `src/easy_cheese/skills/age/commands.py:74-78` and `src/easy_cheese/skills/cure/commands.py:31-35`.

### Report and typed payload

- Age emits `.cheese/age/<slug>.md` at `skills/age/SKILL.md:151-188`.
- Cure reads that file for a slug at `skills/cure/SKILL.md:14-24`.
- The Age phase declares a `CurdPlan` output at `skills/age/phase-contract.yaml:5-10`.
- The Cure phase declares a `CurdPlan` input at `skills/cure/phase-contract.yaml:5-10`.
- Age passes an empty `artifact` and no `baseline` at `skills/age/SKILL.md:112-116`.
- Cure requires a validated plan and confirmed bindings at `skills/cure/SKILL.md:49-75`.
- Runtime validation rejects missing or stale bindings at `src/easy_cheese_schemas/workflow.py:1180-1210`.
- The typed Cure API requires both inputs at `src/easy_cheese_schemas/workflow.py:1305-1329`.

### Commands and errors

- Both bundles expose `findings-cli` through the same shared implementation.
- The command manifests are at `src/easy_cheese/skills/age/commands.py:74-78` and `src/easy_cheese/skills/cure/commands.py:31-35`.
- A missing report or invalid verb becomes a CLI error at `src/easy_cheese/shared/findings_cli.py:20-24,38-43`.
- Unknown identifiers raise `SelectionError` at `src/easy_cheese/shared/findings.py:183-231`.
- Malformed finding rows are ignored at `src/easy_cheese/shared/findings.py:108-155`.
- The valid fixture returned `[1, 2]` from both bundles.
- The main Age syntax fixture returned `[]` from Cure with status zero.
- The low-only fixture had `next: done`, but Cure selected finding `1`.

### Tests

- Age tests cover the report gate and `next: cure` at `tests/python/test_age_review_lock.py:116-185`.
- Cure parser tests use a synthetic correct report at `tests/shared/python/test_findings_cli.py:29-58,121-183`.
- The writer test checks only the Age path and `next` at `tests/shared/python/test_write_handoff_artifact.py:509-532`.
- Typed Cure tests reject missing bindings at `tests/schemas/python/test_workflow_thread.py:846-918`.
- No test sends an Age writer artifact and context into Cure's complete input path.

## Findings by severity

### Blocker

- **Age cannot satisfy Cure's required input.** Age sends Markdown and a locked selection. Cure requires a `CurdPlan` and complete confirmed bindings. The phase files label the payload as `CurdPlan`, but Age emits no typed plan pointer. Fix: add a normal report repair path. Use the typed path only when the handoff supplies its complete inputs.

### High

- **The main Age finding syntax does not match the parser.** `skills/age/SKILL.md:157-164` omits the list marker and location backticks. The parser requires both at `src/easy_cheese/shared/findings.py:45-53`. The worked example uses the parser format at `skills/age/references/report-example.md:59-77`. Fix: specify one exact finding format. Add an Age writer to Cure parser test.
- **A low-only selection has conflicting states.** Age writes `next: done` without a medium finding at `skills/age/SKILL.md:183-188`. Age still selects contained low findings at `skills/age/SKILL.md:200-209`. Cure also selects them at `skills/cure/references/selection.md:3-5,120-135`. Fix: derive `next` from the resolved selection. Use one definition for `medium+`.
- **Press findings cannot reach Cure through the documented command.** Age requests body details at `skills/age/SKILL.md:92-95`. The reader emits preamble fields only at `src/easy_cheese/shared/read_handoff_slug.py:17-40`. Cure reads only the Age report. Fix: read the complete Press report. Copy unresolved items into the Age report.
- **The Age writer can duplicate the handoff preamble.** Age first puts the preamble in the final report at `skills/age/SKILL.md:151-165`. It then passes that report as `--body-file` at `skills/age/SKILL.md:112-116`. The writer prepends another preamble at `src/easy_cheese/shared/write_handoff_artifact.py:106-109`. Fix: write a body-only temporary file. Let the gated writer create the final report.

### Medium

- **Automatic dispatch can drop `--hard`.** Age declares propagation at `skills/age/SKILL.md:40-42`. Its input forms and automatic command omit the flag at `skills/age/SKILL.md:19-21,214-223`. Cure accepts and forwards the flag at `skills/cure/SKILL.md:27-38,227-234`. Fix: add `--hard` to both Age forms. Forward it in every Cure dispatch.

### Low

none

## STE100 status

not compliant

- `skills/age/SKILL.md:128,208,218` has long or combined instructions.
- `skills/cure/SKILL.md:31,45,116,205,221,236,246` has inconsistent terms, capitalization, or voice.
- This note uses short active sentences and one term for each meaning.

## Follow-ups

- Apply the fixes above in the planned Cure node.
- Add one end-to-end Age writer to Cure consumer test.
