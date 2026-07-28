# Worked report example

Read this alongside `SKILL.md § Output` for a concrete rendering of the report skeleton.

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

The worked instantiation above renders only the severity sections. This is the complete report shape, handoff slug through `## Next step`, with every placeholder in context:

```markdown
status: ok | halt: <one-line reason>
next: cure | done
artifact: <path-to-press-report-or-prior-cure-if-any>
durable_flags: none | <one line per flag: what durable knowledge changed -> target wiki page>
baseline: none | <recorded baseline block copied from the upstream handoff — see ../cook/references/quality-gates.md>
<one-line orientation: what the diff does>

press: skipped

<!-- `press: skipped` is the first body line after the blank separator. Omit it entirely when a press report exists for this slug or no cook artifact does. -->

# Age Report — <slug>
## Orientation
<one or two factual sentences about what the diff does>
## Press findings
<omit this section when `.cheese/press/<slug>.md` does not exist. When it does, summarise unresolved press items in one or two bullets so `/cure` (which never reads the press report directly) sees them. When it does not exist but `.cheese/cook/<slug>.md` does, omit this section but add `press: skipped` as the first body line after the handoff slug (see above) instead.>

## Wiki context
<omit this section when hallouminate is absent or grounding returned no hits. When wiki pages informed the review context, list one bullet per consulted page — `<wiki page path>:<line>` — <one-line why it informed the review> — so the user can see, and challenge, what grounded the review.>

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
