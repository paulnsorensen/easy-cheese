# Easy Cheese domain model

<certain> Easy Cheese separates semantic work contracts, workflow continuity, and physical execution. CurdPlan is the semantic work authority. WheypointRecord is the continuity authority. CurdRecord and Milknado plan v2 remain physical/runtime state.

## Workflow continuity

**WheypointRecord** - the living durable continuity authority for one work item across conversations, phases, branches, and worktrees.
_Avoid_: WorkRecord, session, latest note
_Code_: `src/easy_cheese_schemas/wheypoint.py:484`

**WheypointDelta** - a revision-checked semantic update that adds or explicitly transitions protected record state; omission carries state forward.
_Avoid_: note rewrite, implicit deletion
_Code_: `src/easy_cheese_schemas/wheypoint.py:569`

**WheypointRevision** - an immutable resulting record and receipt for one accepted delta, including parent, preservation, provenance, and projection evidence.
_Avoid_: mutable checkpoint, latest file
_Code_: `src/easy_cheese_schemas/wheypoint.py:613`

**WheypointProjection** - generated Markdown for human reading and continuation handoff; it is never the continuity authority.
_Avoid_: authoritative note, continuity database
_Code_: `src/easy_cheese_schemas/wheypoint.py:645`

**WorkAttempt** - one future branch/worktree execution belonging to a WheypointRecord; it owns tentative execution context, phase progress, and artifact links.
_Avoid_: session, Hard Cheese attempt
_Code_: NEW ENTITY

**WorkTask** - one future ordered phase directive claimed by a WorkAttempt and kept nonterminal until completed or explicitly abandoned.
_Avoid_: phase name, background session
_Code_: NEW ENTITY

**AttemptStatePatch** - one future revision-checked lifecycle transition for a WorkAttempt, distinct from curated WheypointDelta context updates.
_Avoid_: implicit unblock, status field edit
_Code_: NEW ENTITY

**WorktreeKey** - local identity derived from a Git worktree-specific Git directory; it groups future active or paused WorkAttempts for deterministic continuation.
_Avoid_: branch key, cwd key
_Code_: NEW ENTITY

**HandoffEnvelope** - a future versioned cross-phase metadata envelope surrounding a phase-owned Markdown report.
_Avoid_: WheypointProjection, unrestricted metadata document
_Code_: NEW ENTITY

**Repo-local Wheypoint snapshot** - an optional portable copy of a WheypointRecord; it is exported explicitly and never becomes a second authority.
_Avoid_: automatic mirror, co-authoritative record
_Code_: NEW ENTITY

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

## Outside-in RED gating

**GateReceipt** - the strict phase-neutral evidence envelope that binds approved work, contract mode, witness disposition, runner argv, protected-file digests, and producer provenance across Cut, Cook, and Press.
_Avoid_: red test file, cut receipt, press receipt, editable handoff
_Code_: `src/easy_cheese_schemas/gates.py`

**TestContract** - Mold-owned executable intent for one acceptance criterion, naming its stable public interface, outer seam, deterministic expected failure, and tracer-or-matrix mode.
_Avoid_: acceptance prose, generated test, test case
_Code_: `src/easy_cheese_schemas/gates.py`

**Cut** - the pre-implementation gate that canonicalizes Test Contracts, adopts or authors the outer test, proves RED, protects evidence by digest, and issues a GateReceipt without committing the red-only state.
_Avoid_: test-writing phase, pre-Cook commit, fixture generator
_Code_: `src/cut/red_gate.py`

**Tracer** - the smallest deterministic causal witness that crosses the approved outer seam for one acceptance criterion.
_Avoid_: unit test, smoke test, contract matrix
_Code_: `mode == "tracer"` in `src/easy_cheese_schemas/gates.py`

**Contract matrix** - the complete uniquely identified behavior rows for a ratified and versioned public API, schema, or protocol.
_Avoid_: parameterized test, many tracers, arbitrary public function tests
_Code_: `mode == "contract-matrix"` in `src/easy_cheese_schemas/gates.py`

**Protected oracle** - the Cut-authored or adopted test and fixture set whose path-safe digests are fixed in the GateReceipt and must remain untouched until final GREEN validation.
_Avoid_: staged test commit, read-only checkout, mutable test plan
_Code_: `protected_files` in `src/easy_cheese_schemas/gates.py`

**Corrective continuation** - a Press-owned bounded return to Cook carrying a producer-`press` GateReceipt for an in-contract production failure exposed by a Press-authored attack.
_Avoid_: Press-to-Cook route, Press production edit, retry
_Code_: `CorrectiveRoute` in `src/fanout/press_route.py:25-31`

**Gate applicability** - Mold's explicit closed classification of requested work as `red-required` behavior or a named `not-applicable` non-behavior class.
_Avoid_: filename heuristic, inferred docs-only, UI exemption
_Code_: `GateApplicability` in `src/easy_cheese/skills/mold/taste_test.py:188`
