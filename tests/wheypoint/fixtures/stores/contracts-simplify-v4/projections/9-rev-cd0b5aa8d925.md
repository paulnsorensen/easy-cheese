status: ok
next: cook
artifact: .cheese/cook/contracts-removal-execution.md
Remove six contracts in three isolated worktrees, then publish the user-approved three-layer stack.

work_id: easy-cheese-contracts-simplify
revision_id: rev-cd0b5aa8d925
record_digest: sha256:6845402169ba5be1a942e38aefc25b40735272f512bdf0b3cd2644d213c198d8
projection_digest: sha256:4e0176455256b8e614cc91e53f148adae5ffd1735c9dcab3cfdb8e419ab63fd1
durability: repo-snapshot
schema_version: 4

# Wheypoint easy-cheese-contracts-simplify @ rev-cd0b5aa8d925

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
- d-0622e1c5c45d (decision) — Publish phase routing, artifact transport, and Cook entry as one three-layer stack.
  rationale: User approves stacking to reconcile shared publication code and generated files.

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
- v-3c4534c9a107 (directive) — Lean toward separate Spec, Plan, and Review contracts; record ownership remains undecided.
  > I'm leaning toward, at least from a schema standpoint, having separate spec, plan, and review contracts at the least. Whether they're in their own record or not I'm not sure.
- v-9210af1e4500 (directive) — Use major-workflow research to inform consolidation, not replace the original type-reduction task.
  > Can we /briesearch further to see what other major workflows do?
- v-ebe0c5ab5004 (directive) — Return to consolidating and reducing existing easy-cheese types; defer premature field-placement questions.
  > The original hand-off was to take our types in eays-cheese and consolidate and reduce them.
- v-cf15115e3ece (directive) — Save this scope/prompting guidance and the research into the existing Wheypoint.
  > Write this, and our research into the /wheypoint we have. <-- deliverable for you
- v-bc946800ab18 (directive) — Inspect the previous stream for deletion candidates and classify their information and original purposes before proposing destinations.
  > Next deliverable, look at our previous stream, and let's figure out which schemas we're already going to delete, and let's categorize which information they have and why they had it, so we can see if they belong in other ones.
- v-2f968dbffee9 (directive) — Inventory required information in current Spec, Review, and Plan items before debating schema shape or storage.
  > Remind me what aspects we have of our current items we have for Spec/Review and Plan , so we can at least consolidate on those rather than bikeshed. Ultimately if we have all the information we aboslutely know we need, irrespective of where it lives, the shapes will pan out.
- v-607bd422641a (directive) — Remove the six first-cut contracts in related groups, one sub-agent and isolated worktree per group, then open PRs.
  > Can you fan out a sub-agent to remove those contracts? Group them by relation, and put one subagent each on those in an isolated worktree and then open PRs
- v-447bd481f379 (directive) — During implementation, show existing analog types and the information they may absorb.
  > Meanwhile , Let's show what contracts we ahve that are these anologs and what parts they are absorbing, aka things like CurdPlan etc.
- v-54548c41a869 (directive) — Stack the three removal PRs in dependency order.
  > Stack the three PRs (recommended)

## Notes

\## Active implementation
User authorizes six removals and three isolated worktrees.
User approves a stack: phase routing → artifact transport → Cook entry.
Use gh-stack; stack-tools reports available (HTTP200), trunk main preflight passes.
No commits, pushes, or PRs exist yet.
Base: 0009f3fa6ef3868c138610a2ce763493d0181b35.
Parent owns review, integration, final gates, commits, submission, and T3 PR linking.

\## Scope
Read .cheese/cook/contracts-removal-execution.md.
Remove public roots and obsolete machinery, not just names.
Preserve integrity, real runner authority, partial-work evidence, and stored user files.
No replacement public envelope, private state-machine clone, migration, or new ontology.
Spec/Plan/Review redesign and fan-out removal remain outside implementation.

\## Worktrees
Workers live under this checkout's .worktrees/.
contracts-phase-routing / worktree/contracts-phase-routing removes phase-contract.
contracts-artifact-transport / worktree/contracts-artifact-transport removes pointer and normalization receipt.
contracts-cook-entry / worktree/contracts-cook-entry removes approval, handoff, preparation result.
Integration baseline: /tmp/easy-cheese-contracts-integration-931a68e5.
Do not run root recursive formatters: they traverse nested worktrees.

\## Verified progress
Pinned baseline just check passes; .cheese/cook/contracts-removal-baseline.md holds evidence.
Phase roots22→21; private five-source/seven-route table replaces registry/compiler/declarations.
Phase taste round2 passes; severity review found dropped active writer tests, assigned to remove_phase_contract.
Parent just check passed before this test restoration.
Transport roots22→20; source net−474 lines before final test restoration.
Transport retains a private operation index and digest/containment/replay checks; historical migration removed.
Wheypoint effective_ref preserves stored bytes; unused receipt helper removed.
Transport taste round2 passes; severity found missing malformed-request-digest tests, assigned to remove_transport.
Full just check passed before this test restoration.
Neither review verified a production defect.
Recheck new test fixes, not unchanged production review.

\## Cook continuation
Two coders made real changes; remove_cook_entry_continue returned needs-context.
Observations: .cheese/cook/remove-cook-entry-context-2.md.
Thirteen preparation modules, prepare/resubmit/accept CLI, and three schema roots are removed.
Direct bound execution and retained setup authority replace gates.
Tracked diff +449/−5436; focused surviving-boundary tests16passed.
Collection/typecheck still fail on obsolete imports; tests/docs/goldens/conformance/bundles need migration.
Branch is not green or reviewed.
Resume fresh coder in same worktree/base; preserve edits and untracked .claude setup.
Move surviving security/scope/replay assertions before deleting mixed test modules.

\## Information discussion and research
Existing analogs: MoldSpecDocument; CurdPlan/SemanticCurd/BoundedScope/BoundedContext/Criterion; ReviewResult/findings/coverage; Wheypoint.
PlannerResult outcome/uncertainty into Plan and ReviewRequest subject/kind/targets into Review remain proposals.
Keep planned checks distinct from CurdResult observed evidence.
Diagnosis and delivery placement remain open.
Research and audit remain linked; rev-44ab1f086024 preserves the information audit.
Do not restart ontology debate or treat agent proposals as user decisions.
Transcript discovery found no Claude transcript; visible turns and preserved entries supply this checkpoint.

\## Latest continuation
remove_cook_entry_tests migrated producer and producer-store tests:32passed.
It returned needs-context with no execution-test edits.
Next bounded worker owns test_cook_execution.py only; context-3 lists exact sites.

## Context

- .worktrees/contracts-cook-entry/tests/python/test_cook_execution.py#1-125
- .worktrees/contracts-cook-entry/tests/python/test_cook_execution.py#224-381
- .worktrees/contracts-cook-entry/src/easy_cheese/skills/cook/preparation/execute.py#1-150

## Artifacts

- xdg:paulnsorensen-easy-cheese/research/context-compilation-work-records/context-compilation-work-records.md (digest: sha256:4c24357272836a6973781d89ce566941fbc2f377b8ab14d2e3b0ba6dab6d4e28, revision: rev-d94ee519b1ad)
- .hallouminate/wiki/architecture/schema-similarity-and-consolidation-audit.md (digest: sha256:04763dbd4c9003ada789b8c019b697e1869cddd9c962bb7b56dd88b4075cef96, revision: rev-d94ee519b1ad)
- https://github.com/steveyegge/beads (revision: rev-d94ee519b1ad)
- https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production (revision: rev-d94ee519b1ad)
- https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md (revision: rev-d94ee519b1ad)
- https://github.com/project-context/context-compiler (revision: rev-d94ee519b1ad)
- https://towardsdatascience.com/coding-agents-dont-need-bigger-context-windows-they-need-a-context-compiler (revision: rev-d94ee519b1ad)
- xdg:paulnsorensen-easy-cheese/research/major-workflow-artifact-contracts/major-workflow-artifact-contracts.md (digest: sha256:896ca3074724544e93490c125462bf22e5c0e5c26956f6b6a3b356801cb4eb67, revision: rev-519cf539b2d8)
- https://developers.openai.com/api/docs/guides/latest-model (revision: rev-519cf539b2d8)
- https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra (revision: rev-519cf539b2d8)
- .cheese/research/contracts-simplify-information-map.md (digest: sha256:80ec9110c61680259fed6d7ea24cd6b16cbc6d32eec9d6e23d1cc655df9532b4, revision: rev-44ab1f086024)
- .cheese/research/contracts-simplify-artifacts.md (digest: sha256:ba97ac78174b58429601d033b28fffc14a68e067472ce234f173c0ccb3d1a634, revision: rev-44ab1f086024)
- .cheese/cook/contracts-removal-execution.md (digest: sha256:eb05ff91b500f15202b3d46a58bf33a3ba3330c8a1524d9cd988cb8450acd72c, revision: rev-e8a12544ab2c)
- .cheese/cook/contracts-removal-baseline.md (digest: sha256:88ed6cfaec0090fe26bc7535b439322e46c215659b50385bba68a6d7f7310b47, revision: rev-270b54db18c5)
- .cheese/cook/remove-cook-entry-context-1.md (digest: sha256:cf43dae2a834ba9f136b70dc8131735e6bb0ee2ad18a5f352e7dc13d3c168c23, revision: rev-60299923901f)
- .cheese/cook/remove-cook-entry-context-2.md (digest: sha256:aea7c3ac6c54d18631d20db220ee3ee30ce31a58a4ae6cc592c3bfb322ab371f, revision: rev-e8a12544ab2c)
- .cheese/cook/remove-cook-entry-context-3.md (digest: sha256:bd1d6a668a2b7abe7315591247e983f7f52c571db329b26117642c02a85154f0, revision: rev-cd0b5aa8d925)

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
Prior leaning: User leans separate contracts. Defer record/storage choice until the information inventory is complete.
- Option: Separate Spec, Plan, and Review payloads embedded in a shared record
  Evidence: research/major-workflow-artifact-contracts/major-workflow-artifact-contracts.md
  Breaks: Requires defined update and revision boundaries; not settled.
- Option: Separate Spec, Plan, and Review payloads linked from work records
  Evidence: research/major-workflow-artifact-contracts/major-workflow-artifact-contracts.md
  Breaks: Requires links and resolution; not settled.
- Option: One Record with typed entry kinds
  Evidence: rev-d94ee519b1ad
  Breaks: Earlier agent leaning only; it must not override the user's current preference for separate contracts.

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
