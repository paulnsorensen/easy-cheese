# Easy-cheese domain model

The workflow-continuity model distinguishes a user's durable work item from branch/worktree executions, queued phase directives, and evidence passed between phases. The approved contract is [Cross-skill work contract](./specs/cross-skill-work-contract.md).

## Workflow continuity

**WorkRecord** — persisted continuity record for one user work item across conversations, phases, branches, and worktrees.
_Avoid_: session, latest note
_Code_: `shared/scripts/work.py`

**WorkAttempt** — one branch/worktree execution belonging to a WorkRecord; it owns tentative execution context, phase progress, and artifact links.
_Avoid_: session, Hard Cheese attempt
_Code_: `shared/scripts/work.py`

**WorkTask** — ordered phase directive created by `next: tasks`; it has deterministic identity, binds to a claiming WorkAttempt, and remains nonterminal until completed or explicitly abandoned.
_Avoid_: phase name, background session
_Code_: `shared/scripts/work.py`

**AttemptStatePatch** — revision-checked explicit lifecycle transition for a WorkAttempt, distinct from curated context edits.
_Avoid_: implicit unblock, status field edit
_Code_: `shared/scripts/work.py`

**WorktreeKey** — local identity derived from a Git worktree-specific Git directory; it groups active or paused WorkAttempts for deterministic continuation.
_Avoid_: branch key, cwd key
_Code_: `shared/scripts/paths.py`

**HandoffEnvelope** — versioned cross-phase JSON metadata surrounding a phase-owned Markdown report.
_Avoid_: positional status header, unrestricted YAML document
_Code_: `shared/scripts/handoff.py`

**PhaseContract** — a human-authored YAML declaration of a source phase's payload schema and permitted outgoing transitions; it is compiled at build time.
_Avoid_: universal payload schema, runtime YAML dependency
_Code_: `skills/<phase>/references/handoff-contract.yaml`

**Global transition registry** — build-assembled validation model containing every globally addressable workflow phase, destination-only contracts, and reserved control outcomes, independent of current harness installation.
_Avoid_: local availability list
_Code_: compiled into `skills/cheese/scripts/cheese.pyz`

**Repo-local work snapshot** — optional portable copy of a WorkRecord under `.cheese/work/`; imported or exported explicitly and never a second authority.
_Avoid_: automatic mirror, co-authoritative record
_Code_: `shared/scripts/work.py`

## Semantic work contracts

**CurdPlan** - the canonical semantic description of executable work, checks, dependencies, and bounded shared context.
_Avoid_: CurdBlock, Decomposition, Milknado plan
_Code_: NEW ENTITY

**Semantic Curd** - one independently verifiable unit inside CurdPlan with outcome, scope, inputs, outputs, dependencies, and checks.
_Avoid_: CurdRecord, batch node
_Code_: NEW ENTITY

**CurdBlock** - Easy Cheese's lossless legacy and physical projection of representable CurdPlan work.
_Avoid_: canonical plan
_Code_: src/easy_cheese_schemas/curd.py:148

**Decomposition** - a lossless migration projection of representable CurdPlan work.
_Avoid_: canonical plan
_Code_: src/easy_cheese_schemas/decomposition.py:39

**CurdRecord** - mutable runtime dispatch state whose integer id is distinct from semantic curd_id.
_Avoid_: semantic curd
_Code_: src/easy_cheese_schemas/manifest.py:345

**PlannerRequest** - a typed decompose, remediate, or replan request carrying evidence.
_Avoid_: CurdExecutionRequest
_Code_: NEW ENTITY

**PlannerResult** - the planner disposition and optional valid CurdPlan.
_Avoid_: Decomposition
_Code_: NEW ENTITY

**ReviewResult** - typed review findings plus a coverage ledger; it never creates curds.
_Avoid_: remediation plan
_Code_: NEW ENTITY

**DiagnosisResult** - reproduction, hypotheses, optional confirmed cause, regression seam, and unresolved evidence.
_Avoid_: fix handoff, remediation plan
_Code_: NEW ENTITY

**CurdResult** - one criterion-led semantic result per input curd.
_Avoid_: Milknado node result, CurdRecord
_Code_: NEW ENTITY

**ArtifactRef** - canonical content identity validated for URI policy, digest, size, media type, and optional schema.
_Avoid_: Wheypoint ArtifactLink, universal runtime envelope
_Code_: NEW ENTITY

**EvidenceRef** - a typed reference to evidence used by planning, review, diagnosis, or verification.
_Avoid_: embedded log
_Code_: NEW ENTITY

**SourceLocation** - a bounded location inside referenced evidence.
_Avoid_: raw path string
_Code_: NEW ENTITY

**AgentWriterView** - the slim payload an agent authors before deterministic host normalization.
_Avoid_: canonical artifact
_Code_: NEW ENTITY

**ContractVersion** - host-authored schema identity and major/minor version metadata.
_Avoid_: agent-authored version, version range negotiation
_Code_: NEW ENTITY

**UnsupportedProjection** - typed evidence that a legacy projection cannot preserve CurdPlan semantics.
_Avoid_: lossy conversion
_Code_: NEW ENTITY

**PhaseContract** - a phase-local declaration of payload schema URIs and allowed destinations.
_Avoid_: universal payload schema, handoff body schema
_Code_: NEW ENTITY

**TransitionRegistry** - the build-compiled authority used by helpers to validate phase transitions.
_Avoid_: Global transition registry, hard-coded helper table
_Code_: NEW ENTITY

**source_plan_ref** - physical-projection provenance containing semantic plan ID, revision, and digest.
_Avoid_: runtime plan ID
_Code_: NEW ENTITY

**source_curd_ref** - physical-item provenance containing semantic curd ID and digest.
_Avoid_: Milknado node ID
_Code_: NEW ENTITY