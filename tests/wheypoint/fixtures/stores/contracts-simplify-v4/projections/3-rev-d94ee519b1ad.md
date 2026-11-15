status: ok
next: culture
artifact: 
Contracts thread, session 1: gates go first, the wheypoint is the backbone, and artifacts must not force the mold-cook-age-cure chain.
The user reframed the artifacts as context compilation over an ontology of records of varying weight, each cooked through an optional curd plan.
Research found no prior art that combines all parts; next move is /culture on one Record contract with typed entry kinds versus separate artifact contracts.

work_id: easy-cheese-contracts-simplify
revision_id: rev-d94ee519b1ad
record_digest: sha256:a0926957f241cc1bf649269d786aed0c847645c1ba8430eac84d4d44e6e8a5c0
projection_digest: sha256:d5b9240718a935773eae3b688d06da420925cf0165dfcb62927a0ac7176b095c
durability: repo-snapshot
schema_version: 4

# Wheypoint easy-cheese-contracts-simplify @ rev-d94ee519b1ad

## Gates

none

## Open entries

- q-5436fe56ebcb (question) — Which of the 22 contracts survive scrutiny, and do spec, eval-result, and artifact-ref get registered?
- q-46e11cadc258 (question) — Is the ontology one Record contract with typed entry kinds (requirement, criterion, decision, piece, finding, question), or separate Spec, Plan, and Review contracts linked to the backbone?
- q-ce7ee5e5c909 (question) — Does the delivery plan fold into the Plan as optional pr_group, branch, and stack_order fields on pieces, with no grouping meaning one PR?
- q-2309d2baacc0 (question) — Which survival test decides public contracts: A (an LLM writes and code reads), B (a durable artifact), or C (either)? The backbone directive may make this moot.
- q-7c2925b3fdec (question) — Do execution results fold into Plan piece status and evidence, and does diagnosis become a Review kind? Both are agent proposals the user has not confirmed.
- q-b0f30b16f5f2 (question) — Is the compiled per-task context a projection over the wheypoint graph (ADK style) or a ready-queue selection (Beads style)?
- q-ce51636ad3f9 (question) — What sets plan weight (omitted, inline, or full): a code-scored complexity as in Taskmaster, or an agent or user choice as in OpenSpec lite?
- q-a8eb95ada04b (question) — Under a one-Record model, how do spec prose and diagrams fit, given the 6000-character notes cap and the parent's open living-spec fork?
- q-f20da4e6d72c (question) — How does one generator emit both the agent writer view and the host-complete shape for each kind, per the wiki consolidation audit?
- q-7693caed7458 (question) — Does any external reader consume schemas.easy-cheese.dev, and do removed contract URIs need a deprecation path?
- q-2c95b0520e09 (question) — Do the fan-out-bound contracts (remediation-state, remediation-cure-observation, review-request, diagnosis-request, pr-plan) leave with the stack, pending the parent's fan-out fork?

## Decisions

- d-c4f8f176780b (decision) — Gates are the first cut; re-add any gate later only on demonstrated need.
  rationale: User call: the gates mostly create difficulties. Candidates are mold-cook-approval, mold-cook-handoff, cook-preparation-result, handoff-pointer, normalization-receipt, and phase-contract; approvals become wheypoint decision entries.

## Directives

- v-2848b9e6bf27 (directive) — A rebuild keeps the pyz and keeps exported, shareable schemas and code.
  > I like the pyz, and i like the idea of having schemas and code thats exported and shareable.
- v-435d499ac025 (directive) — Use code to limit nondeterminism; the main goal is lower token cost.
  > My philosophy is still to limit nondetermism by using code but mostly to save token cost.
- v-05792ad32014 (directive) — Test whether the project is overbuilt and whether every skill still makes sense at the end of 2026.
  > But i wonder how much weve overbuilt and if all the skills still make sense at the end of ghe year 2026.
- v-f06f46c0ab3d (directive) — Use easy-cheese schemas for the main artifacts of the spec to curd-plan to execution/eval loop.
  > we want to use cheese schemas for the actual main artifacts of spec -> curdplan -> execution/eval loop
- v-266b6ad0bc08 (directive) — Scrutinize every schema: the 21 registered contracts and the 4 proposed ones.
  > i want to scrutinize all of the schemas we have come up with
- v-846a9e89cea5 (directive) — The contracts thread aims for extreme simplification of the easy-cheese schema contracts.
  > I'd like to fork a new wheypoint off of this to focus on the contracts. I think we need to extremely simplify here
- v-062a98957685 (directive) — Cut the gates first; they can come back later.
  > There are fair amount of gates that mostly create difficulties, so I think those are the first to go. We can re-add them later.
- v-2f476f0f49a5 (directive) — The wheypoint is the backbone; specs, implementation plans, delivery plans, and review results are the high-level drivers.
  > The high-level things that drive us are clearly wheypoint as the backbone, then specs, implementation plans, delivery plans, review-results i guess.
- v-74217e31c08e (directive) — Unify the artifacts so that work does not have to pass through the bespoke mold-cook-age-cure workflow.
  > I think  we want to try to unifiy this in a way that doesnt force us to go through a bespoke mold cook age cure workflow (as pointed out in the previous wheypoint).
- v-b6bdb1f63db7 (directive) — Treat objects as context compilation: an ontology of records of varying weight (prototypes, specs, reviews), each cooked through a curd plan that is inline or omitted when trivial.
  > ontology of records, which may have verying degrees of specs and decisions (depending on the size) - prototypes, specs, reviews, whathaveyou, they all get cooked using a curd plan (which cna be as simple as inline, or omitted if its trivial)

## Notes

\## State
Session 1 of the contracts thread (2026-10-04): no source change, no commit.
The user steered from contract triage to a consolidation model, then to context compilation over a typed record ontology.
The open fork at stop: one Record contract with typed entry kinds, or separate artifact contracts linked to the backbone.

\## Contract inventory (measured)
- 22 contracts are registered in `_schema_catalog.py`; `work-edge` was the promoted proposal. Still proposed: spec, eval-result, artifact-ref. `MoldSpecDocument` (contracts.py:3021) and `ArtifactRef` (contracts.py:599) already exist unregistered.
- Families: wheypoint 4 (record, revision, checkpoint-intent, work-edge); spec-plan-execute 6 (mold-cook-handoff, mold-cook-approval, cook-preparation-result, curd-plan, curd-result, handoff-pointer); request/result pairs 6 (planner, review, diagnosis); remediation 2; plumbing 3 (agent-writer-view, normalization-receipt, phase-contract); publish 1 (pr-plan).
- Every contract has a runtime consumer outside tests. `phase-contract` has none in src/easy_cheese. `review-request` and `diagnosis-request` are only dispatch-callback types (workflow.py:84-85).
- 12 of 22 tie to the fan-out, remediation, or checkpoint stack.
- Package: 10,163 lines; contracts.py 4,410, schema_runtime.py 1,404, compat.py 683, planner.py 617, manifest.py 525.
- About 17 WriterView classes (contracts.py:2126-2560, about 430 LOC) mirror 6 canonical contracts. The split is deliberate (ADR workflow-contract-milknado-seam-002); the wiki audit says merge the generator, not the shapes. Correction: the agent first claimed option B removes the split; that claim was wrong.
- Schemas publish to schemas.easy-cheese.dev through Cloudflare Pages (scripts/build_schema_site.py, schemas-site.yml). A removed URI is an external change; external readers are unknown.
- Single-use enums: ReviewKind, PlannerRequestKind, CurdDisposition, WriterViewKind, IngressKind, NormalizationActionKind, RemediationDisposition, PerLayerGreen, ReviewFixes.
- Churn since 2026-06-01: 43 commits; hottest AgentWriterView, ReviewResult, CurdPlan, CheckpointIntent, RemediationState; non-contract MoldSpecDocument (about 943 lines changed).

\## Consolidation proposal (agent, not user-approved)
- Gates become wheypoint decision entries: mold-cook-approval, mold-cook-handoff, cook-preparation-result, handoff-pointer, normalization-receipt.
- Delete phase-contract; it encodes the bespoke pipeline.
- Private: planner-request, review-request, diagnosis-request.
- Leave with fan-out: remediation-state, remediation-cure-observation.
- Merge: planner-result plus curd-plan into Plan; curd-result into Plan piece status; diagnosis-result into a Review kind.
- pr-plan becomes DeliveryPlan, then optional grouping on Plan pieces (pr_group, branch, stack_order); absent means one PR.
- Public set went 22 to 5 (Record, Spec, Plan, DeliveryPlan, Review) to 4, then the context-compilation idea points to 2 (Record plus a typed entry union).
- Workflow-agnostic rule: no artifact names the phase that made it. Edges (implements, informs, supersedes) carry relations; the next move derives from graph state. mold, cook, and age become verbs over records.

\## Context compilation (agent synthesis)
- The wheypoint is already half a compiler: typed entries, edges, working_context, projection, resolve.
- Store: the wheypoint graph. Compiler: deterministic pyz code selects records along edges, compresses, emits a per-task packet.
- The plan is the universal execution unit: omitted, inline piece entries, or its own linked record.
- One-Record cost: kind-specific payloads (file:line findings, criteria, prose and diagrams) and the 6000-character notes cap.

\## Research
Report: research/context-compilation-work-records (ground-check 0 errors; budget-check not run, no manifest). No surveyed source combines typed work records, per-task compilation, and no fixed phases. ADK: "context is a compiled view over a richer stateful system". Beads: typed issue graph, 10 edge kinds, ready queue. OpenSpec: phase-free, lite mode, delta merge into a living spec. Taskmaster: complexity 1-10 sets subtask expansion (inferred). No tool puts delivery planning in the plan. project-context/context-compiler is README-only; the TDS compiler is code-only. Unchecked: Devin, Factory, Agent OS, Letta, DSPy.

\## Process gotchas
- wheypoint `turns` needs `--session <id>`; it refuses recency.
- ground-check misreads a footnote glued to a path (`raw/x.md[^a]`); put a space before the marker.
- briesearch budget-check needs manifest.json; researcher agents write only calls.jsonl.

## Context

- src/easy_cheese_schemas/_schema_catalog.py
- src/easy_cheese_schemas/contracts.py
- src/easy_cheese_schemas/mold_cook.py
- src/easy_cheese_schemas/pr_plan.py
- src/easy_cheese_schemas/phase_contracts.py
- src/easy_cheese_schemas/schema_runtime.py
- src/easy_cheese_schemas/compat.py
- src/easy_cheese/shared/workflow.py
- src/easy_cheese/shared/fanout/remediation_decision.py
- src/easy_cheese/shared/fanout/validate_pr_plan.py
- scripts/build_schema_site.py
- scripts/_schema_catalog_compiler.py
- .github/workflows/schemas-site.yml
- .hallouminate/wiki/architecture/schema-similarity-and-consolidation-audit.md
- .hallouminate/wiki/adr/workflow-contract-milknado-seam-002.md
- .hallouminate/wiki/adr/skill-boundary-normalization-002.md
- .hallouminate/wiki/adr/wheypoint-ergonomics-003.md

## Artifacts

- xdg:paulnsorensen-easy-cheese/research/context-compilation-work-records/context-compilation-work-records.md (digest: sha256:4c24357272836a6973781d89ce566941fbc2f377b8ab14d2e3b0ba6dab6d4e28, revision: rev-d94ee519b1ad)
- .hallouminate/wiki/architecture/schema-similarity-and-consolidation-audit.md (digest: sha256:04763dbd4c9003ada789b8c019b697e1869cddd9c962bb7b56dd88b4075cef96, revision: rev-d94ee519b1ad)
- https://github.com/steveyegge/beads (revision: rev-d94ee519b1ad)
- https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production (revision: rev-d94ee519b1ad)
- https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md (revision: rev-d94ee519b1ad)
- https://github.com/project-context/context-compiler (revision: rev-d94ee519b1ad)
- https://towardsdatascience.com/coding-agents-dont-need-bigger-context-windows-they-need-a-context-compiler (revision: rev-d94ee519b1ad)

## Links

- forked_from wheypoint:paulnsorensen-easy-cheese/rebuild-easy-cheese-from-scratch@rev-c1a85e43507b @rev-0f767b91e3e9
  rationale: fork of rebuild-easy-cheese-from-scratch@rev-c1a85e43507b; moved: q-471b1a429aa5, v-094b05325867; copied: v-2ed986ad7bb1, v-6dbfeb3c409b, v-0cb361d7bb2e, v-f369ada77674; dossier: none; links: none

## Lineage

- forked_from wheypoint:paulnsorensen-easy-cheese/rebuild-easy-cheese-from-scratch@rev-c1a85e43507b
- q-5436fe56ebcb origin wheypoint:paulnsorensen-easy-cheese/rebuild-easy-cheese-from-scratch@rev-c1a85e43507b#q-471b1a429aa5
- v-2848b9e6bf27 origin wheypoint:paulnsorensen-easy-cheese/rebuild-easy-cheese-from-scratch@rev-c1a85e43507b#v-2ed986ad7bb1
- v-435d499ac025 origin wheypoint:paulnsorensen-easy-cheese/rebuild-easy-cheese-from-scratch@rev-c1a85e43507b#v-6dbfeb3c409b
- v-05792ad32014 origin wheypoint:paulnsorensen-easy-cheese/rebuild-easy-cheese-from-scratch@rev-c1a85e43507b#v-f369ada77674
- v-f06f46c0ab3d origin wheypoint:paulnsorensen-easy-cheese/rebuild-easy-cheese-from-scratch@rev-c1a85e43507b#v-0cb361d7bb2e
- v-266b6ad0bc08 origin wheypoint:paulnsorensen-easy-cheese/rebuild-easy-cheese-from-scratch@rev-c1a85e43507b#v-094b05325867

## Decision dossier

### Fork: Record ontology shape
Prior leaning: Agent leans one Record with typed entry kinds (speculating); the user has not chosen.
- Option: One Record contract with typed entry kinds
  Evidence: src/easy_cheese_schemas/contracts.py:3540
  Evidence: raw/b-adk.md in research/context-compilation-work-records
  Evidence: https://github.com/steveyegge/beads
  Breaks: Entries need kind-specific payloads, and spec-sized records exceed the 6000-character notes cap.
- Option: Separate Spec, Plan, and Review contracts linked by ArtifactLink and WorkEdge
  Evidence: src/easy_cheese_schemas/contracts.py:3652
  Evidence: src/easy_cheese_schemas/contracts.py:3670
  Breaks: The compiler needs one adapter per kind, and record weight lives in several schemas.
- Option: Artifacts embedded as typed payload sections of the wheypoint record
  Evidence: src/easy_cheese_schemas/contracts.py:3896
  Breaks: The record grows without bound, every spec edit becomes a record revision, and sharing a spec shares the whole record.

### Fork: Public contract survival test
Prior leaning: Agent leaned A after the consumer map; the backbone directive may supersede the test.
- Option: A: an LLM writes and code reads
  Evidence: src/easy_cheese_schemas/_schema_catalog.py:29
  Evidence: src/easy_cheese/shared/workflow.py:84
  Breaks: wheypoint-record stays private although other tools would read it.
- Option: B: a durable artifact that outlives a session
  Evidence: src/easy_cheese_schemas/_schema_catalog.py:29
  Breaks: Agent output envelopes lose public schemas, so retry-saving validation is internal only.
- Option: C: either test
  Evidence: src/easy_cheese_schemas/_schema_catalog.py:29
  Breaks: About 11 contracts survive, which is less simple.

### Fork: Delivery plan placement
Prior leaning: Agent leans fold into Plan pieces.
- Option: Optional grouping fields on Plan pieces
  Evidence: src/easy_cheese/shared/fanout/validate_pr_plan.py
  Evidence: src/easy_cheese_schemas/pr_plan.py:234
  Breaks: A post-build stack split becomes a Plan revision.
- Option: Separate DeliveryPlan contract
  Evidence: research/context-compilation-work-records/context-compilation-work-records.md
  Breaks: A trivial change with no plan still needs a delivery document.

### Fork: Context compiler shape
Prior leaning: Not stated.
- Option: Projection over the wheypoint graph, rebuilt per task
  Evidence: https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production/
  Breaks: The compiler must define selection and compression passes for each entry kind.
- Option: Ready-queue selection with show and claim
  Evidence: https://github.com/steveyegge/beads
  Breaks: Context is the selected item only, with no assembled background.

### Fork: Plan weight scaling
Prior leaning: Not stated.
- Option: Code-scored complexity sets omitted, inline, or full
  Evidence: https://github.com/eyaltoledano/claude-task-master
  Breaks: The score needs calibration, and the inference about default expansion is unverified.
- Option: Agent or user choice with a lite default
  Evidence: https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md
  Breaks: Weight becomes nondeterministic, against the code-first directive.
