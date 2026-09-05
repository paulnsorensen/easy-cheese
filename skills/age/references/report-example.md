# Worked report example

Read this with `SKILL.md § Output` for a concrete report skeleton.

## Body order

Write the body in this order.
Start with `# Age Report — <slug>`.
Add `## Orientation` with 1-2 sentences.
Add `## Press findings` only when a press report exists.
Add `## Wiki context` only when hallouminate grounding returns a hit.
Add `## Agent resolution` after the severity sections.
Use the exact three-line form below for each finding.
`/cure` parses this form with `src/easy_cheese/shared/findings.py`.
A finding that drops the list marker or the location backticks is invisible to `/cure`.

```markdown
- **[<dim>:<sev>]** `path:line` — <claim>
  - location: <tier> · fix-cost-now: <tier> · fix-cost-later: <tier> · confidence: <tier>
  - recommendation: <action>
```

End with `## Confidence` and `## Next step`.
The worked instantiation and the full skeleton follow below.

Omit empty severity sections.
When ten or more `low` findings exist, collapse the `## Low` section to one line:

```markdown
## Low
*N low-severity findings suppressed.* Re-run with `--full` (or `/age --full`) to see them.
```

```markdown
## Blocker
- **[encapsulation:blocker]** `src/users/index.ts:42` — `index` re-exports `SqlPgUser` (infra ORM type) across slice boundary. 3 consumer slices already import it.
  - location: contract · fix-cost-now: sprawling · fix-cost-later: structural · confidence: certain
  - recommendation: define `User` in the slice's public types, map at the boundary, deprecate the leaked export.

## High
- **[security:high]** `src/api/admin/users.ts:55` — admin route accepts user-supplied filter without validation.
  - location: contract · fix-cost-now: contained · fix-cost-later: contained · confidence: certain
  - recommendation: validate against `AdminFilter` schema at boundary.

## Medium
- **[complexity:medium]** `src/utils/format.ts:200-240` — 60-line function, 5 params.
  - location: module · fix-cost-now: contained · fix-cost-later: contained · confidence: speculating
  - recommendation: extract `formatHeader` / `formatBody`.

## Low
- **[deslop:low]** `src/utils/format.ts:18` — variable `data` shadows outer `data`.
  - location: class · fix-cost-now: contained · fix-cost-later: contained · confidence: certain
  - recommendation: rename to `lineItems`.

## Confidence
<`certain` | `speculating` | `don't know`> — <one-line justification including which evidence sources were unavailable>

## Next step
<when press was skipped, lead with>: Hardening was skipped for this diff — run `/press <slug>` before curing, or continue reviewing as-is.
Auto-fixing the recommended set via `/cure` (or the selection prompt on a reason to ask / `--safe`).
```

## Full skeleton (with placeholders)

The worked instantiation above renders only the severity sections. This is the complete report shape, handoff slug through `## Next step`, with every placeholder in context. Use the canonical `status:` grammar from the [handback contract](../../cheese/references/handback-contract.md):

```markdown
status: <canonical status field>
next: cure | done
artifact: <path-to-press-report-or-prior-cure-if-any>
durable_flags: none | <one line per flag: what durable knowledge changed -> target wiki page>
baseline: none | <recorded baseline block copied from the upstream handoff — see ../../cook/references/quality-gates.md>
<one-line orientation: what the diff does>

press: skipped

<!-- `press: skipped` is the first body line after the blank separator. Omit it entirely when a press report exists for this slug or no cook artifact does. -->

# Age Report — <slug>
## Orientation
<one or two factual sentences about what the diff does>
## Press findings
<omit this section when `.cheese/press/<slug>.md` does not exist.
When that report exists, copy each unresolved press item into one or two bullets.
`/cure` never reads the press report, so an item that is absent here never reaches `/cure`.
When the press report is absent and `.cheese/cook/<slug>.md` exists, omit this section.
Add `press: skipped` on the first body line instead.>

## Wiki context
<omit this section when hallouminate is absent.
Omit it when grounding returned no hit and `/cheese` routed no `wiki_hits`.
List one bullet for each consulted page: `<wiki page path>:<line>` — <one line on why it informed the review>.
The user reads this section to challenge what grounded the review.>

## Blocker
<one row per blocker, in the finding format above. Omit this section when no blocker exists.>

## High
<one row per high finding. Omit this section when no high finding exists.>

## Medium
<one row per medium finding. Omit this section when no medium finding exists.>

## Low
<one row per low finding. Omit this section when no low finding exists.
Collapse this section to one line when ten or more low findings exist.>

## Agent resolution
<one bullet per resolved worker: role, selected type, effort, and `degraded: true` when a fallback ran.>

## Confidence
<`certain` | `speculating` | `don't know`> — <one line on the evidence, including each unavailable source>
<one bullet per escalated claim that the verifier could not settle, with the missing evidence>

## Next step
<when press was skipped, lead with>: Hardening was skipped for this diff. Run `/press <slug>` before curing, or continue the review.
<then state the selection>: Fixing the recommended set through `/cure`.
<or, on a reason to ask or `--safe`>: Rendering the selection prompt.
```

Read the worked instantiation above for the finding rows that these placeholders stand for.
