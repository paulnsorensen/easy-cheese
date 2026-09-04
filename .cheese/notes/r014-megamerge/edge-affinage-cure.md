# Affinage to Cure Edge Review

## State

`broken`

Affinage and Cure agree on publication ownership.
Their input, selection, and result contracts do not agree.

## Evidence

| Contract | Affinage side | Cure side | State |
| --- | --- | --- | --- |
| Host dispatch | `skills/affinage/SKILL.md:193-205`; `skills/affinage/references/handoff-templates.md:40-56` | `skills/cure/SKILL.md:12-21`; `skills/cure/references/selection.md:21-41` | broken |
| Handoff fields | `skills/affinage/references/handoff-templates.md:45-51` | `skills/cure/references/selection.md:26-38` | broken |
| Report path | `skills/affinage/SKILL.md:92-95`; `skills/affinage/references/handoff-templates.md:47-50` | `skills/cure/SKILL.md:14-20`; `skills/cure/references/selection.md:23-45` | broken |
| Finding grammar | `skills/affinage/references/report-template.md:19-32,40-44` | `src/easy_cheese/shared/findings.py:40-53,108-132`; `src/easy_cheese/shared/findings_cli.py:20-24,38-43` | broken |
| Typed execution | `skills/affinage/references/handoff-templates.md:42-51` | `skills/cure/SKILL.md:49-75`; `src/easy_cheese_schemas/workflow.py:1180-1210,1305-1328` | broken |
| Cure result | `skills/affinage/SKILL.md:101-109` | `skills/cure/SKILL.md:135-180` | broken |
| Publication owner | `skills/affinage/SKILL.md:204-205,229-234`; `skills/affinage/references/handoff-templates.md:53-56` | `skills/cure/SKILL.md:190-194`; `skills/cure/references/auto-mode.md:22-38` | ok |
| Flags | `skills/affinage/SKILL.md:33-56,212-227` | `skills/cure/SKILL.md:27-38,236-250` | ok |
| Imports and commands | `src/easy_cheese/skills/affinage/commands.py:14-59` | `src/easy_cheese/skills/cure/commands.py:31-35,66-96` | host dispatch only |
| Tests | `tests/shared/python/test_findings_cli.py:29-58` | `tests/shared/python/test_findings_cli.py:124-173` | untested |

The Python areas do not import each other.
Affinage invokes the Cure skill through the host dispatch.
Cure uses `findings-cli` to parse and select report findings.

The handoff sends `source_skill`, `source_report`, `selection`, and `resolved_ids`.
Cure requires only `selection` and `resolved_ids` in its prose.
Cure uses `source_skill` only to retain publication ownership.
Cure does not define a type or validation rule for `source_report`.

## Findings

### Blocker

- **[spec:blocker] The typed Cure path cannot consume the Affinage handoff.**
  Affinage supplies no `PlannerResult`, `CurdPlan`, or `CureDiagnosisBinding`.
  Cure requires these values and stops when the plan is absent.
  Evidence: `skills/affinage/references/handoff-templates.md:42-51`; `skills/cure/SKILL.md:49-75`; `src/easy_cheese_schemas/workflow.py:1180-1210`.
  **Fix:** Give report handoffs a direct repair path. Reserve typed Cure for Cook handoffs.

### High

- **[correctness:high] The Cure parser silently drops every Affinage finding.**
  Affinage puts a provenance tag before each dimension tag.
  The Cure parser requires the dimension tag first and returns an empty list.
  The bundle probe returned `[]` with status zero.
  Evidence: `skills/affinage/references/report-template.md:19-32,40-44`; `src/easy_cheese/shared/findings.py:40-53,108-132`; `src/easy_cheese/shared/findings_cli.py:20-24,38-43`.
  **Fix:** Accept the Affinage grammar in the shared parser. Preserve provenance in `Finding.extra`. Reject a nonempty report that parses empty.

- **[spec:high] Cure does not consume the producer's `source_report` field.**
  Affinage points `source_report` at `.cheese/affinage/pr-<n>.md`.
  Cure still resolves `<slug>` under `.cheese/age/`.
  Cure defines no missing-field or wrong-source error.
  Evidence: `skills/affinage/references/handoff-templates.md:45-51`; `skills/cure/SKILL.md:14-20`; `skills/cure/references/selection.md:23-45`.
  **Fix:** Load `handoff_context.source_report` first. Validate the source area and file. Stop with one defined error when validation fails.

### Medium

- **[spec:medium] The Cure result does not preserve the reply contract.**
  Affinage reads `### Applied` and `### Deferred` from `.cheese/cure/pr-<n>.md`.
  Cure only promises named sections under `.cheese/cure/<slug>.md`.
  Cure does not bind the slug or preserve each comment identifier.
  Evidence: `skills/affinage/SKILL.md:101-109`; `skills/cure/SKILL.md:135-180`.
  **Fix:** Bind the Cure slug to the source report stem. Require exact headings and `[from-comment:<id>]` on each result.

- **[assertions:medium] Tests do not exercise this seam from either side.**
  The checked `tests/**` tree has no `handoff_context`, `source_report`, `resolved_ids`, or Affinage report fixture.
  Existing parser tests use only the Age report grammar.
  Evidence: `tests/shared/python/test_findings_cli.py:29-58,124-173`.
  **Fix:** Add a producer contract test and a consumer contract test. Cover selection, result mapping, errors, and publication ownership.

### Low

none

## Contract drift

- Affinage now emits an Affinage report path and provenance-first findings. Cure still accepts the Age path and Age grammar.
- Cure now requires a typed plan and confirmed diagnosis bindings. Affinage still emits only a report and locked selection.
- Both skills retain Affinage as the publication owner. This contract has no drift.

## STE100 status

noncompliant

- `skills/affinage/SKILL.md:44,51,84,194` combines multiple instructions in one sentence.
- `skills/affinage/SKILL.md:76,111,217` uses three terms for the fresh review.
- `skills/cure/SKILL.md:31,236` uses two terms for automatic mode.
- `skills/cure/SKILL.md:45` starts a sentence with a lowercase word.

This note uses active voice, one instruction per sentence, and consistent terms.

## Follow-ups

- Add a normal report repair path for Affinage handoffs.
- Align the Affinage report grammar with the Cure parser.
- Define the Cure result mapping for Affinage replies.
- Add producer and consumer seam tests.
