# Scope interrogation

Use this procedure before judging the change or dispatching reviewers.
Reuse the diff, requirements, and project context already collected.
Do not add a separate agent, approval gate, or mandatory user interview.

## Facts before judgment

Inventory the actual changes with file and line citations:

- Database tables, columns, indexes, and migrations.
- Scheduled jobs, background workers, and their triggers.
- Features added or modified.
- External services, APIs, and dependencies.
- Environment variables, configuration flags, and their consumers.
- Public endpoints and interfaces.
- Deleted or deprecated behavior.

Keep each applicable category visible; group related changes rather than listing every symbol.
Mark an unchanged category as none within the reviewed scope.
Do not open with approval or infer purpose from names such as reliability, maintenance, or flexibility.
For an overall review, distinguish existing mechanisms from changes in the supplied range.

## Establish necessity

Map each addition to a cited requirement, user decision, or demonstrated technical constraint.
Distinguish documented intent from inferred purpose and unknown intent.
Include supplied product constraints and future plans; do not invent future consumers.
Give reviewers this context with the relevant inventory entries.

Challenge unclear additions with evidence-based questions:

- What requirement fails if we remove this?
- Why can the existing table, service, helper, or dependency not meet that requirement?
- Who changes this flag from its default, and for which supported task?
- Which current consumer needs this abstraction?
- Which parts exceed the requested behavior?

When a runtime task exists, trace it from its real entrypoint to its observable result.
When input rejection applies, trace an invalid input to its rejection point and the test that proves rejection.
Name live boundaries that the tests do not cover.

For each disputed addition, record its purpose, evidence, simpler alternative, and removal consequence.
An unclear explanation is a question, not proof that code is unnecessary.
Check counterevidence before agreeing with a leading question or recommending deletion.
Use the parent skill's user-input rule for missing intent.
Continue independent review work while that question remains open.

## Report and follow-up

Put the factual inventory and requirement mapping before findings under `## Change inventory`.
Keep unresolved intent questions there and reflect their effect under `## Confidence`.
Grade supported defects under the existing dimensions, such as spec, complexity, or NIH.
Do not turn missing intent alone into a finding or an automatic deletion recommendation.
Keep correctness, security, and failure-path review; scope interrogation does not replace them.
When the user supplies new context, identify which conclusions change and cite the new evidence.
Follow the existing late-evidence rules; do not change locked evidence in place.

## Example

Request: notify the admin when a service returns error codes.
Observed change: two new tables store email and Slack delivery status.
Ask which requirement needs persistent delivery state and whether the existing notification service can send the notice.
If an approved audit requirement needs that state, retain it and cite the requirement.
If existing delivery meets all requirements, report the duplicate state and its concrete maintenance cost.
If intent remains unknown, report the question rather than ordering table deletion.
