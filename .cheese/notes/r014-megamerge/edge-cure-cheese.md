# Cure to Cheese Edge Review

## State

broken

Cure follows Cheese for source routing and basic portability.
The handback and resume contracts do not agree at HEAD.

## Evidence

| Surface | Cure side | Cheese side | State |
| --- | --- | --- | --- |
| Contract references | Cure links routing, portability, handback, handoff, formatting, and agent contracts (`skills/cure/SKILL.md:44,104,148,177,209,283`). | Cheese owns each linked contract under `skills/cheese/references/`. | ok |
| Runtime imports | Cure imports shared command helpers only (`src/easy_cheese/skills/cure/commands.py:7-63`). | Cheese remains a read-only router (`skills/cheese/SKILL.md:64-73`). | ok |
| Command inventory | Cure exposes eight commands (`src/easy_cheese/skills/cure/commands.py:66-96`; `tests/python/test_pyz_bundle.py:81-90`). | The writer, reader, and handoff commands carry the Cheese handback contract. | broken |
| Emitted file | Cure writes `.cheese/cure/<slug>.md` (`skills/cure/SKILL.md:97-99,135-179`). | Cheese declares each phase report resumable (`skills/cheese/references/handback-contract.md:67-90`). | broken |
| Resume lookup | Cure emits a registered phase report. | Cheese routes each resume through Wheypoint (`skills/cheese/SKILL.md:107-118`). | broken |
| Resume implementation | Cure supplies a valid handoff preamble. | Wheypoint accepts projections and `.cheese/notes/` fallbacks only (`src/easy_cheese/skills/wheypoint/resolve.py:118-144,179-203`; `src/easy_cheese/skills/wheypoint/legacy.py:330-366`). | broken |
| Required fields | Cure names `status`, `next`, `artifact`, `baseline`, and orientation (`skills/cure/SKILL.md:135-149`). | Cheese requires `status`, `next`, `artifact`, and orientation (`skills/cheese/references/handback-contract.md:15-32`). | broken |
| Status routing | Cure documents only `ok` and `halt` (`skills/cure/SKILL.md:164-173`). | Cheese requires routing by disposition (`skills/cheese/references/handback-contract.md:34-65`). | broken |
| Status consumption | Cure can use every canonical writer status. | Cheese resumes only exact `ok` and handles `gated` and `halt` separately (`skills/cheese/references/continue-resume.md:98-129`). | broken |
| Artifact meaning | Cure uses the undefined value `<path-if-any>` (`skills/cure/SKILL.md:141-159`). | Cheese defines the field as the consumed prior report (`skills/cheese/references/handback-contract.md:30-32`). | broken |
| Terminal state | Cure permits `next: done` (`skills/cure/SKILL.md:168-171`). | Cheese stops on `next: done` (`skills/cheese/references/continue-resume.md:170-181`). | broken |
| Safe gate | Cure names four choices and immediate execution (`skills/cure/SKILL.md:209-219`). | Cheese requires one action for each option and immediate execution (`skills/cheese/references/handoff-gate.md:56-79,100-111`). | ok |
| Source edits | Cure requires a fresh read and a stale-safe edit (`skills/cure/SKILL.md:64-65,102-107`). | Cheese defines the same sequence (`skills/cheese/references/code-intelligence-routing.md:18-30`). | ok |
| Reviewer fallback | Cure permits an inline check when fresh context is unavailable (`skills/cure/SKILL.md:83-90`). | Cheese requires a halt when fresh-context isolation is unavailable (`skills/cheese/references/agent-resolution.md:65-71`). | broken |
| Tests | Cure has static field checks (`tests/python/test_ultracook_skills.py:242-252`). | Cheese tests generic resume branches, but not Cure reports (`tests/wheypoint/python/test_resolve.py:730-780`). | untested |

The other five Cure commands do not cross this edge.
They are `slugify`, `findings-cli`, `gates-cli`, `paths-cli`, and `render-html`.

## Findings by severity

### Blocker

- **Cheese cannot resume a Cure report.**
  Cure writes `.cheese/cure/<slug>.md`, and the handback contract assigns Cheese as its consumer.
  Cheese sends every resume reference to Wheypoint.
  Wheypoint rejects an exact Cure path and ignores Cure reports during slug lookup.
  A HEAD probe returned `not-found` for the slug.
  The same probe returned `invalid-reference` for the absolute path.
  **Fix:** Accept exact registered phase reports after strict handoff validation.
  Require a selection when one slug identifies multiple reports.
  Never select a report by time.

- **The documented writer removes the Cure report body.**
  Cure writes the report before it runs `write-handoff-artifact` (`skills/cure/SKILL.md:97-99,151-159`).
  The command omits `--body-file`.
  The writer then replaces the report with only the preamble (`src/easy_cheese/shared/write_handoff_artifact.py:106-109,164-197`).
  A HEAD probe removed `# Cure report` and its `Applied` section.
  Cheese defines a durable report as the preamble plus body (`skills/cheese/references/handback-contract.md:67-88`).
  **Fix:** Write the body to a separate file.
  Pass that file through `--body-file`.
  Add a regression test that preserves every report section.

- **Cheese does not route the canonical status dispositions.**
  The handback contract requires consumers to branch on `proceed`, `retry`, or `stop` (`skills/cheese/references/handback-contract.md:34-65`).
  Cheese resumes only exact `status: ok` (`skills/cheese/references/continue-resume.md:109-120`).
  It has no resume action for `ok-with-concerns` or `needs-context`.
  The runtime preserves both statuses (`tests/wheypoint/python/test_resolve.py:730-769`).
  **Fix:** Parse the canonical disposition before Cheese selects an action.
  Proceed with the concern attached.
  Retry Cure once with the named gap.
  Stop on `gated` or `halt`.

### High

- **The writer example cannot emit Cure's terminal state.**
  Cure permits `next: done`, but its command always writes `--next age` with a result schema.
  A terminal transition rejects every payload schema (`src/easy_cheese/shared/write_handoff_artifact.py:47-58`).
  A HEAD probe returned exit code 3 for `next: done` with the shown schema.
  **Fix:** Show one command for `next: age`.
  Show a second command for `next: done`.
  Omit `--payload-schema` from the terminal command.

- **Cure can lose baseline state before Cheese resumes.**
  Cure requires a copied `baseline:` value (`skills/cure/SKILL.md:138-149`).
  Its writer example omits `--baseline` and `--durable-flags` (`skills/cure/SKILL.md:151-159`).
  `handoff-cli` also omits `baseline` during render and parse (`src/easy_cheese/shared/handoff_cli.py:29-75,88-101`).
  Cheese treats baseline state as settled (`skills/cheese/references/continue-resume.md:178-181`).
  A HEAD probe parsed a valid baseline and then omitted it from the JSON output.
  **Fix:** Pass each present optional field to the writer.
  Add `baseline` support to both `handoff-cli` directions.
  Test the complete Cure preamble through Cheese resume.

- **Cure does not define `artifact:` as the prior report.**
  Cure uses `<path-if-any>`, which does not identify the required source.
  Cheese requires the consumed prior report (`skills/cheese/references/handback-contract.md:30-32`).
  Cure can consume an Age report and a typed planner artifact.
  The current prose does not select one canonical pointer.
  **Fix:** Define one typed artifact reference for Cure.
  State its allowed source and validation rules.
  Make Cheese forward that value without inference.

- **Cure weakens the fresh-context failure mode.**
  Cure permits an inline check when its reviewer is unavailable.
  Cheese requires a halt when required fresh-context isolation is unavailable.
  These instructions can produce two different review strengths for the same gate.
  **Fix:** Use the shared agent resolver.
  Halt when the required fresh context is unavailable.
  Allow an inline check only under a documented small-diff exception.

### Medium

- **No test exercises the complete Cure-to-Cheese seam.**
  The focused suite passed 292 tests.
  The Cure check asserts only three field names in prose (`tests/python/test_ultracook_skills.py:242-252`).
  Generic tests cover the writer, status parser, and legacy notes separately.
  They all pass while the real Cure report fails both resume forms.
  **Fix:** Write a Cure report through the bundled writer.
  Resolve it through Cheese and Wheypoint.
  Assert the next dispatch, prior artifact, body, optional fields, statuses, and terminal state.

### Low

none

## Verification

- The focused handoff, schema, Wheypoint, and prose tests passed with 292 tests.
- The Cure slug resume probe returned `not-found`.
- The Cure path resume probe returned `invalid-reference`.
- The writer probe removed the report body.
- The terminal writer probe returned exit code 3.
- The handoff parser probe omitted `baseline`.

## STE100 status

not compliant

- `skills/cure/SKILL.md:45` starts a sentence with a lowercase word.
- `skills/cure/SKILL.md:31,236` uses two terms for automatic mode.
- `skills/cure/SKILL.md:205,221,246` uses different terms for post-PR write-back.
- `skills/cheese/SKILL.md:136` has a procedural sentence longer than 20 words.
- `skills/cheese/references/code-intelligence-routing.md:23` has a procedural sentence longer than 20 words.
- `skills/cheese/references/handback-contract.md:74-77` has a descriptive sentence longer than 25 words.
- `skills/cheese/references/handoff-gate.md:141` has a procedural sentence longer than 20 words.
- `skills/cheese/references/harness-portability.md:19` has a procedural sentence longer than 20 words.
- This review note complies with the required writing rules.

## Follow-ups

- Repair Cure report resolution through Cheese and Wheypoint.
- Preserve the Cure body and every optional handoff field.
- Add separate writer commands for review and terminal states.
- Route every canonical status by disposition.
- Define one `artifact:` meaning for Cure.
- Enforce the shared fresh-context failure mode.
- Add one end-to-end Cure-to-Cheese contract test.
