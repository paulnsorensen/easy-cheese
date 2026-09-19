# Shared context packet

The coordinator builds one packet at `.cheese/age/<slug>-packet.md` before the review lock.
Save the contextual request and returned plan beside it.
Do not add a preliminary classifier or mandatory context agent.
Reuse evidence gathered while identifying the review target.
Every review rebuilds its packet; there is no persistent cross-run cache.

## Components

1. **Target and requirement** — Identify the exact diff or overall scope, source snapshot, and located specification or issue. State when no specification exists. For a specification, include its fired `leverage:` triggers.
2. **Component roles** — Include relevant dependency manifests and the component/path map. Distinguish library exports, application entry points, tests, build systems, and documentation.
3. **Shared impact evidence** — Include changed symbols, caller and callee relationships, affected contracts, and relevant enclosing functions. Collect these once with the selected code-intelligence backend.
4. **Project-helper index** — Detect source roots from manifests or changed paths. Find task-relevant existing helpers such as sanitization, validation, escaping, retry, and logging mechanisms.
5. **Instruction sources** — Include review-instructions output with source identities, scope, hashes, and line citations. Distinguish collected candidates from host-supplied active instructions. Report unresolved authority or unavailable sources explicitly.
6. **Context and plan** — Include subject applicability, risk evidence, policy version, input digest, assignments, capability restrictions, and dispatch batches. A zero workload weight never removes a path from relevance analysis.
7. **Rubrics and severity** — Give workers their subject procedures and primary dimension rubrics, plus location sensitivity, fix-cost-now, fix-cost-later, and severity computation. Link the other rubrics for findings outside the primary set.
8. **Output and ownership** — Include the exact per-finding format, `also-relevant-to`, applicable `invariants` from `report-example.md`, and the reconciliation contract below.

## Primary rubric map

Subjects are investigation procedures, not restrictions on which findings a worker can report.
Use this map to prepare the initial rubric material without copying the whole repository into every worker prompt.

| Subject | Primary dimensions |
| --- | --- |
| changed-behavior | correctness, telemetry, security |
| removed-behavior | correctness, spec, assertions |
| caller-impact | correctness, encapsulation |
| security | security |
| spec-tests | spec, assertions |
| reuse | nih, deslop |
| simplification | complexity, deslop |
| efficiency | efficiency |
| conventions | conventions |
| altitude | altitude, encapsulation, complexity |

Extract rubric sections by their dimension headings from `dimensions.md`.
Combined assignments receive the union of the relevant rubrics.
A worker that identifies another kind of problem reads that rubric before classifying its finding.

## Evidence views

Conventions and altitude receive the whole-change orientation and component relationships.
Other workers receive their assigned targets and the relevant shared evidence sections.
Workers may inspect additional code when evidence requires it; target scopes are starting points, not excuses to miss affected callers.
A security assignment names its trust boundary, not every test file in the repository.
The altitude view includes the owning component and immediate consumers so it can evaluate solution placement.
An optional explorer can resolve a genuinely unmapped area; it is not a fixed prerequisite for every review.

## Output and reconciliation ownership

Workers emit full finding rows and `also-relevant-to: [<dimension>, ...]` where another rubric may apply.
Pass every candidate with a nameable failure scenario or concrete design cost through; verification filters it later.
Workers do not deduplicate, apply boundary tiebreakers, reconcile severity, edit source, or write the canonical report.
The coordinator reconciles by the underlying problem and applies the dimension boundary rules.
A shared line does not prove duplicate findings, and one defect can span several locations.

## Transient evidence contract

Write the request, plan, instruction-source output, and packet before capturing the review lock.
Give workers read-only access.
Do not mutate locked evidence or preserve it as a cross-run cache.
If new observations require replanning, preserve the prior plan and record the changed context.
A production-tree change requires a new review, not a refreshed lock that makes stale findings appear current.
Leave transient artifact removal to normal `.cheese/` cleanup.

## Late evidence

The report write can fail with `review evidence changed`. The error names each moved `.cheese/` file.
This error means that the source tree still matches the lock. Only review evidence moved, for example a late packet.
Run `python3 skills/age/scripts/age.pyz review-lock --slug <slug> --refresh-evidence`. Then write the report again.
The refresh refuses when a source file moved.
Record the refresh and the named files under `## Agent resolution` in the report.
Every other lock failure stays final. Do not take a new lock to force the write.

## Evidence tools and fallbacks

Use `../../cheese/references/code-intelligence-routing.md` for backend selection.
Use symbol-aware caller and dependency queries when available; report weaker evidence when only text search is available.
Reuse supplied wiki citations before searching again.
Optional Hallouminate context can explain design intent; cite its pages and mark inference-based claims as speculating.
Use GitHub tools for PR context, or local Git and user-provided data when GitHub is unavailable.
Optional integrations follow `../../cheese/references/optional-plugins.md`; state an absence once and use the documented fallback.
No missing optional integration authorizes a fabricated source or a silent coverage claim.
