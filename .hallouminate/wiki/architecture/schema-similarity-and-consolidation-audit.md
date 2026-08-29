---
status: reviewed
last_verified: 2026-08-29
confidence: high
sources:
  - src/easy_cheese_schemas/
  - src/easy_cheese/shared/
  - .hallouminate/wiki/adr/workflow-contract-milknado-seam-001.md
  - .hallouminate/wiki/adr/workflow-contract-milknado-seam-002.md
  - .hallouminate/wiki/adr/workflow-contract-milknado-seam-003.md
  - .hallouminate/wiki/adr/workflow-contract-milknado-seam-004.md
---

# Schema similarity and consolidation audit

The Easy Cheese schema package should consolidate implementations and authorities, not collapse its eleven registered contract roots. The audit found **zero safe root-contract merges**, **three concrete consolidation programs**, and **four supporting opportunities**. The central distinction is semantic: two records can look structurally similar while serving different authors, trust boundaries, lifecycles, or persistence obligations.

The three recommended programs are:

1. finish the accepted migration from **CurdBlock** and **Decomposition** to **CurdPlan** as the sole semantic work authority;
2. replace the three independently implemented test-contract shapes with one shared definition plus stage-specific projections;
3. make the attrs **PrPlan** model the only PR-topology authority, generate its JSON Schema, and make fan-out, manifest, and Plate consume validated projections or references.

The supporting opportunities are:

- one private directed-acyclic-graph validation kernel;
- one gate-applicability policy source;
- reference-based RunManifest integration with GateReceipt, Wheypoint, and PrPlan;
- shared private value validators for repeated source spans, criterion text, checks, and identifiers.

These changes reduce duplication without erasing the seams that make the workflow auditable.

## Scope

This audit covers every model and enum under **src/easy_cheese_schemas/**, the eleven registered validation roots, and the adjacent shared/runtime models that duplicate or project schema concepts.[^1] It also includes the proposed Milknado RoadmapModel because graph ownership is the design pressure that triggered the review.[^2]

“Schema” has three meanings in the repository, and confusing them produces bad consolidation decisions:

1. **Registered contract root** — a versioned payload accepted by the schema runtime.
2. **Published model** — a Python type exported by easy-cheese-schemas but not necessarily registered as a standalone validation root.
3. **Projection or envelope** — a compatibility, transport, persistence, or agent-writing view of another authority.

The package currently has eleven registered roots at version 1.0: ten JSON contracts and one Markdown document contract.[^3] A repository-wide symbol inventory also found 97 attrs models and 48 enums. That larger number is expected because nested value objects, legacy projections, persistence records, and writer views live beside the registered roots.[^1]

## Method

Nineteen read-only Luna agents independently inspected individual roots or coherent schema families. Each produced a qualitative “embedding”: a semantic fingerprint rather than a textual similarity score. A final comparison agent examined the complete set.

The normalized dimensions were:

| Dimension | Question |
| --- | --- |
| Authority | Is this the source of truth, a projection, evidence, or runtime state? |
| Author | Human, agent, host normalizer, executor, or scheduler? |
| Consumer | Which phase or external system relies on it? |
| Lifecycle | Ephemeral call, immutable artifact, mutable run state, or continuity snapshot? |
| Trust boundary | What is untrusted, computed, or already known by the host? |
| Identity | Does it own identity, refer to identity, or derive identity? |
| Versioning | Registered schema version, document format version, or unversioned internal model? |
| Graph semantics | Semantic dependency DAG, physical execution DAG, or no graph? |
| Evidence semantics | Findings, diagnosis, criterion outcomes, or artifact integrity? |
| Side effects | Pure description, execution command, publication state, or recovery state? |
| Persistence | Canonical persisted artifact, generated view, or transient request? |
| Loss model | Is projection required to be lossless, deliberately slim, or a summary? |

No numeric cosine score is recorded. The source fingerprints used different local scales, and converting them into a single number would create false precision. Consolidation is instead accepted only when authority, lifecycle, trust boundary, and loss model agree.

## Registered contract inventory

| Root | Role | Authority and lifecycle | Consolidation verdict |
| --- | --- | --- | --- |
| agent-writer-view | Generated slim schema for agent-authored output | Transient authoring boundary; host normalizes to canonical form | Keep separate from canonical contracts |
| curd-plan | Canonical semantic work graph | Persisted semantic authority | Keep; absorb legacy authorities through projections |
| curd-result | Criterion-led executor outcome | One canonical result per semantic curd | Keep separate |
| diagnosis-request | Input to diagnostic reasoning | Transient request envelope | Keep separate |
| diagnosis-result | Structured diagnostic evidence | Persisted evidence artifact | Keep separate |
| phase-contract | Declares payload schemas and allowed destinations | Static routing metadata | Keep separate |
| planner-request | Input to semantic planning | Transient request with typed evidence | Keep separate |
| planner-result | Planning disposition and optional plan | Persisted planner decision | Keep separate |
| review-request | Input to review | Transient request envelope | Keep separate |
| review-result | Findings plus coverage ledger | Persisted review evidence | Keep separate |
| mold-spec | Human-readable specification document | Markdown authoring and approval contract | Keep separate |

The registry maps the ten JSON names to attrs roots and registers **mold-spec** through the document-contract path. The runtime derives deterministic Draft 2020-12 schemas, validates exact named contracts, and canonicalizes bytes and digests.[^3]

## Published families outside the root registry

The following families are part of the public schema surface or operational contract map even though they are not all standalone registered roots:

| Family | Purpose | Relationship to roots |
| --- | --- | --- |
| CurdBlock | Legacy physical/fan-out shape | Lossless-only projection from CurdPlan |
| Decomposition | Legacy planning shape | Lossless-only projection from CurdPlan |
| GateReceipt | Persisted evidence that a gate ran or was inapplicable | References work/results; not a result replacement |
| RunManifest | Mutable run-level coordination and audit state | Aggregates references and execution metadata |
| PrPlan | PR topology and stack plan | Owns publication graph, not semantic work |
| Wheypoint | Conversation continuity checkpoint | Recovery snapshot, not execution state |
| ArtifactRef | Canonical content-addressed artifact identity | Shared primitive used by contracts |
| ArtifactLink | Operational pointer/link record | Related to ArtifactRef but not interchangeable |
| Loaded and ResolvedAgentArtifact | Trust-boundary resolution products | Runtime wrappers around validated artifacts |
| CanonicalArtifact | Canonical serialized payload plus identity | Persistence envelope |
| CureDiagnosisBinding | Explicit bridge from diagnosis evidence to Cure | Cross-phase binding, not a new diagnosis |
| Benchmark records | Conformance and quality measurements | Test/analysis data, not workflow roots |

## Similarity clusters

### Request envelopes

PlannerRequest, ReviewRequest, and DiagnosisRequest all contain version identity, a subject, and bounded input references. Their structural similarity is real and should be expressed through shared primitives such as ContractVersion, ArtifactRef, EvidenceRef, BoundedScope, and BoundedContext.[^4]

They should not share a public “GenericRequest” root:

- PlannerRequest chooses among decompose, remediate, and replan and carries typed evidence.
- ReviewRequest defines review scope and requested review behavior.
- DiagnosisRequest frames a symptom and diagnostic boundary.
- Each is validated at a different phase boundary and evolves under different domain pressure.

A generic root would either become a union of unrelated optional fields or erase phase-specific validation. The correct consolidation level is nested values and runtime plumbing.

### Result envelopes

PlannerResult, ReviewResult, DiagnosisResult, and CurdResult all report a disposition and structured payload. That is superficial similarity.

Their meanings are incompatible:

- PlannerResult decides whether executable semantic work exists.
- ReviewResult is findings plus an explicit coverage ledger.
- DiagnosisResult is evidence culminating in an optional confirmed cause and regression seam.
- CurdResult is one criterion-led outcome per semantic curd.

The existing ADRs deliberately keep review and diagnosis as evidence, planning as the only decomposition authority, and execution results criterion-led.[^5] A generic Outcome or Result root would weaken required-field rules and invite invalid state combinations.

### Planning and graph models

CurdPlan, CurdBlock, Decomposition, PrPlan, RunManifest wiring, and RoadmapModel all contain nodes and relationships, but they represent different graphs.

| Model | Graph meaning | Node identity | Edge meaning |
| --- | --- | --- | --- |
| CurdPlan | Semantic work | opaque curd_id | semantic prerequisite |
| CurdBlock | Legacy fan-out placement | legacy curd identity | legacy dependency/projection |
| Decomposition | Legacy planning | legacy item identity | reduced dependency semantics |
| PrPlan | Publication topology | PR-plan item | branch/stack dependency |
| RunManifest wiring | Runtime dispatch topology | runtime curd record | scheduled dependency |
| RoadmapModel | Authoring/lifecycle graph | goal ID | goal dependency |

CurdPlan is already accepted as the sole semantic authority. CurdBlock and Decomposition are explicitly lossless-only projections and must fail when they cannot represent the canonical plan.[^6] This is consolidation by retirement, not by inventing a broader graph root.

PrPlan must remain separate because PR topology changes when branches, stacks, or publication strategy change; those changes must not alter semantic curd identity. RunManifest wiring remains runtime state. RoadmapModel remains an authoring and lifecycle graph.

What should be shared is a private DAG kernel that validates:

- unique node IDs;
- references to existing nodes;
- no self-dependencies;
- acyclicity;
- deterministic topological ordering;
- useful error paths;
- optionally, model-specific edge constraints supplied by the caller.

The kernel must not own node payloads, identity namespaces, lifecycle state, or serialization. Those remain in the domain models.

### Test and gate models

Three definitions currently express essentially the same user-facing test contract:

1. Mold TestContractRow in the document schema;
2. gates.TestContract in gate execution;
3. shared.taste_test.TestContract in Taste Test orchestration.[^7]

They share the same core intent: a named check, command or procedure, expected behavior, and ownership/applicability metadata. Independent implementations create drift in field names, requiredness, and validation.

This is the strongest new type-level consolidation candidate. Define one canonical shared TestContract value object in easy-cheese-schemas, then expose projections where stages need different presentation:

- Mold document row: author-friendly tabular syntax;
- execution gate: validated operational form;
- Taste Test: review-oriented form with applicability disposition.

GateApplicability, Taste Test’s RedRequired/NotApplicable choice, and GateReceipt disposition also describe one policy question: **must this gate run for this work?**[^8] They should derive from one policy source while retaining distinct storage shapes.

GateReceipt must not merge with CurdResult. A receipt proves a gate was executed, skipped under policy, or found inapplicable; CurdResult reports semantic criterion outcomes. One may reference the other.

### Persistent state and continuity

RunManifest and Wheypoint are both durable JSON-like records, but their lifecycles differ.

RunManifest is mutable operational state for a run: wiring, attempts, gate summaries, and execution bookkeeping.[^9] Wheypoint is a conversation-continuity snapshot designed to resume intent and context after interruption.[^10]

Merging them would couple recovery format changes to runtime orchestration and encourage the checkpoint to become an unbounded copy of execution state. Keep both roots.

RunManifest should, however, stop copying mature cross-domain state. Prefer validated references to:

- GateReceipt for detailed gate evidence;
- Wheypoint for continuity;
- PrPlan for publication topology;
- canonical CurdPlan and CurdResult artifacts for semantic input and output.

The manifest may retain compact indexed summaries required for admission or status display, but each summary must name its authority and be reproducibly derived. This recommendation needs a dedicated spec because migration, atomicity, and offline readability are design constraints.

### Artifact references and links

ArtifactRef and ArtifactLink overlap in URI/path/media metadata but serve different layers.

ArtifactRef is canonical integrity-bearing identity: URI policy, SHA-256 digest, size, media type, and optional schema. The resolver then exposes a slim agent view.[^11] ArtifactLink is an operational link/pointer used by persistence and handoff machinery.[^12]

Do not merge them. Instead, give ArtifactLink an explicit conversion or containment relationship to ArtifactRef when integrity is known. A link without verified content identity must not silently satisfy an ArtifactRef boundary.

### Canonical artifacts and writer views

Canonical and writer forms are intentionally different. Agents omit invocation-known IDs, digests, versions, provenance, coverage, and other host-computable fields; deterministic normalizers add them and reject contradictions.[^13]

AgentWriterView must therefore remain a separate registered root. The duplication visible in writer/canonical pairs is deliberate boundary compression, not redundant schema design. Consolidate the generator and field annotations, not the public shapes.

### Phase routing and artifact semantics

PhaseContract owns allowed destinations and payload-schema references. It does not own payload fields, runtime capability availability, or continuity. The compiled TransitionRegistry validates the global phase graph.[^14]

PhaseContract should not merge with HandoffPointer, AcceptedArtifact, RunManifest, or Wheypoint. Routing policy, transport identity, runtime state, and continuity are separate concerns.

## Concrete consolidation programs

### Program 1: finish CurdPlan authority migration

**Status:** already decided by accepted ADR.

Target state:

- CurdPlan is the only semantic work authority.
- CurdBlock and Decomposition are compatibility projections only.
- New code cannot construct either legacy form as independent semantic input.
- Every projection is lossless or returns UnsupportedProjection with the curd and field that cannot be represented.
- CurdRecord retains mutable dispatch state and separate runtime identity.
- Milknado physical plans retain source_plan_ref and source_curd_ref.

Expected reduction: three competing semantic shapes become one authority plus temporary adapters. This removes two legacy authorities without reducing the eleven registered roots, because the legacy shapes are not registered roots.

Exit criteria:

1. no workflow path accepts CurdBlock or Decomposition as authoritative input;
2. all remaining conversions originate from validated CurdPlan;
3. compatibility tests cover every unsupported field;
4. documentation and generated bundles no longer teach legacy authoring;
5. retirement dates or deletion conditions are explicit.

### Program 2: canonical shared TestContract

**Status:** recommended; not yet an accepted architecture decision.

Target state:

- one frozen schema value object owns semantic test fields and invariants;
- Mold’s Markdown compiler parses rows into that object;
- gate execution consumes the operational projection;
- Taste Test consumes the review projection;
- applicability is resolved by the shared policy source;
- generated document rules and JSON Schemas come from the same definition.

Required design decisions:

1. whether command and procedure are alternatives or one normalized execution description;
2. how human-readable expected behavior maps to machine-verifiable acceptance;
3. whether ownership is a phase, role, or free text;
4. whether applicability belongs inside TestContract or beside it;
5. how legacy rows migrate without accepting ambiguous empty values.

Success is not merely deleting classes. A single malformed test contract must fail consistently at Mold validation, gate execution, and Taste Test.

### Program 3: make PrPlan the only PR-topology authority

**Status:** recommended; current code demonstrates drift.

The attrs PrPlan and the hand-authored JSON Schema disagree. The JSON Schema requires plate_layout and permits pr_number/pr_url fields that the attrs model does not own; dependency validation is also split across consumers.[^15]

Target state:

- attrs PrPlan is canonical;
- its JSON Schema is generated deterministically;
- fan-out validates through easy-cheese-schemas;
- manifest stores a reference or generated summary;
- Plate consumes the validated plan or a publication-state projection;
- topology checks, including depends_on validity and cycle checks, live with the model or shared DAG kernel;
- publication outputs such as PR number and URL live in a distinct publication-result/state model, not in the planning input.

This preserves the useful boundary between “what PR topology should exist?” and “what was published?”

## Supporting consolidation opportunities

### Shared DAG validator

Implement one private algorithm with domain callbacks. It should return structured failures containing the model name, node ID, edge, and cycle path. Do not publish a GenericGraph schema.

Potential consumers:

- CurdPlan;
- legacy CurdBlock and Decomposition validation during migration;
- RunManifest WiringRow validation;
- PrPlan;
- proposed RoadmapModel.

### Shared gate-applicability policy

Define a single resolver over normalized work metadata and gate kind. Stage-specific representations may remain:

- policy decision;
- Taste Test RedRequired/NotApplicable view;
- GateReceipt persisted disposition.

The resolver should make “not applicable” distinguishable from “not run,” “blocked,” and “failed.”

### Manifest reference architecture

Specify which RunManifest fields are authorities and which are indexes. For every copied summary, define:

- source artifact;
- derivation function;
- freshness rule;
- behavior if the source artifact is unavailable;
- whether the summary is included in the manifest digest.

This work should follow CurdPlan and PrPlan authority cleanup so the manifest references stable objects.

### Private value validators

Repeated source-span and criterion validation should move behind small private helpers or shared value objects. Candidate repetitions include:

- SourceLocation and writer-view span ordering;
- non-empty criterion/check text;
- identifier syntax;
- unique ID collections;
- dependency-reference validation.

The public domain types should remain explicit. Shared validation code is valuable only when it preserves equal error semantics.

## Rejected consolidations

| Proposed merge | Verdict | Reason |
| --- | --- | --- |
| PlannerRequest + ReviewRequest + DiagnosisRequest | Reject | Different phase semantics and required payloads |
| PlannerResult + ReviewResult + DiagnosisResult + CurdResult | Reject | Different authorities, evidence meanings, and completeness rules |
| GateReceipt + CurdResult | Reject | Gate execution evidence is not semantic criterion outcome |
| RunManifest + Wheypoint | Reject | Mutable execution state is not conversation continuity |
| ArtifactRef + ArtifactLink | Reject | Integrity-bearing identity is not an operational pointer |
| AgentWriterView + canonical payload | Reject | The trust boundary requires deliberate asymmetry |
| PhaseContract + HandoffPointer | Reject | Routing policy is not transport identity |
| PhaseContract + RunManifest | Reject | Static transition metadata is not mutable execution state |
| CurdPlan + PrPlan | Reject | Semantic work graph is not publication topology |
| CurdPlan + RoadmapModel | Reject | Executable work is not authoring/lifecycle state |
| ReviewFinding + DiagnosisHypothesis | Reject | Review observation and causal hypothesis have different proof obligations |
| One global Outcome enum | Reject | Shared labels conceal incompatible state machines |

## Drift and gaps discovered

### Planner version-policy mismatch

The accepted writer-boundary ADR says older supported minors validate against their registered schema and normalize forward, while the later boundary simplification work calls for exact-version equality at the writer boundary. The inspected Planner request validator still accepts older minors.[^16]

Resolve this explicitly rather than blending the policies. The recommended interpretation is:

- canonical stored contracts may support registered older minors and normalization;
- an agent writer-view invocation validates exactly the version supplied for that invocation.

The final rule needs a conformance test and an ADR correction if this interpretation differs from the approved simplification.

### Mold parser under-enforcement

MoldSpecDocument defines more structure than the current Mold runtime parser enforces. The gaps include frontmatter constraints and Test Contract row validation.[^17] Program 2 should close this by making the document compiler produce the canonical shared TestContract.

### ReviewKind is not enforcing dispatch

ReviewKind is present in the schema but was optional or unused in the inspected workflow dispatcher. This permits schema intent and runtime behavior to diverge.[^18] Either make it operationally authoritative or remove it from the boundary after a compatibility review.

### Named but unimplemented boundary artifacts

NormalizationReceipt, AcceptedArtifact, and PublishedArtifact appear in architecture prose and specs but no corresponding implementation symbols were found in the inspected schema and workflow sources.[^19] Confidence is medium because the search covered repository code and wiki references, not every historical branch.

Before adding new graph exports, decide whether these names are still required contracts, conceptual states represented by existing models, or abandoned design vocabulary.

### PrPlan schema drift

The attrs model, hand-authored JSON Schema, fan-out validator, and Plate consumer do not express one exact contract.[^15] This is an active trust-boundary risk because different callers can accept incompatible payloads.

### Document-rule duality

Document rules are compiled for schema use while Mold also maintains runtime parsing logic.[^20] Generated rules are appropriate, but there must be one source of truth and parity tests between document validation and runtime consumption.

## RoadmapModel boundary

The proposed RoadmapModel should be exported from easy-cheese-schemas only if Easy Cheese is intended to own the interoperable graph-document contract and Milknado imports it. The current Milknado model contains lifecycle state, GoalDocument, RoadmapDocument, graph validation, and JSON Schema generation.[^21]

Its boundary should remain:

- RoadmapModel owns authoring structure, lifecycle, goal dependency validity, and document serialization.
- CurdPlan owns executable semantic work and acceptance.
- Milknado physical plans own batches, nodes, retries, and execution topology.
- A compiler translates approved roadmap goals into planning input or CurdPlan.
- The shared private DAG validator provides mechanics but no cross-domain node type.

An unresolved fork is the location of DocumentStatus and lifecycle policy. It can remain in Milknado while the structural graph moves, or move with RoadmapModel if Easy Cheese owns the complete document contract. That decision affects import direction and should be settled in the graph-flow-schemas spec, not implicitly during refactoring.

## Recommended execution order

1. **Freeze the inventory.** Add a generated/export manifest test for registered roots, public schema types, and schema URIs.
2. **Repair drift first.** Align PrPlan, Mold document enforcement, and writer-version policy before introducing new shared abstractions.
3. **Finish accepted CurdPlan retirement work.** Remove remaining alternative-authority paths.
4. **Extract the private DAG kernel.** Migrate one consumer at a time with exact error tests.
5. **Unify TestContract.** Add parity fixtures across Mold, gates, and Taste Test.
6. **Unify gate applicability.** Make all dispositions derive from the same policy.
7. **Specify manifest references.** Avoid changing persistence without migration and offline-read rules.
8. **Place RoadmapModel.** Export it only after ownership and lifecycle status are decided.
9. **Regenerate schemas and bundles.** Confirm deterministic output.
10. **Run the repository gate.** just check is the only local shippability signal.[^22]

## Verification criteria

The consolidation effort is complete when:

- every registered root has one documented authority and lifecycle;
- no two public models claim the same semantic authority;
- CurdBlock and Decomposition can only be obtained as fallible projections;
- all test-contract entry points accept and reject the same semantic cases;
- PrPlan Python validation and generated JSON Schema are identical in meaning;
- each graph domain rejects missing references, self-edges, duplicate IDs, and cycles through the shared kernel;
- RunManifest copied fields are either removed or documented as derived indexes;
- writer-view and canonical validation policies are explicit and tested;
- schema generation is deterministic;
- all skill bundles consume the schema distribution rather than private duplicate models;
- just check passes.

## Decision ledger

### Already decided

- CurdPlan is the sole semantic work authority.
- CurdBlock and Decomposition are lossless-only projections.
- The planner alone owns semantic decomposition.
- Review and diagnosis are evidence, not work plans.
- Executors consume CurdPlan and emit one criterion-led CurdResult per semantic curd.
- Agents write slim views; hosts normalize canonical artifacts.
- Phase routing metadata remains distinct from payload schemas and runtime state.

### Strong recommendations awaiting a spec or ADR

- One shared TestContract definition with stage projections.
- One attrs-authored and generated PrPlan contract.
- One private DAG validation kernel.
- One gate-applicability policy source.
- Reference-oriented RunManifest composition.
- RoadmapModel and its schema move to easy-cheese-schemas if Easy Cheese owns the interoperable graph document.

### Open decisions

- Exact-versus-compatible minor-version policy at each trust boundary.
- Ownership of DocumentStatus and roadmap lifecycle transitions.
- Whether NormalizationReceipt, AcceptedArtifact, and PublishedArtifact become concrete contracts.
- RunManifest migration and offline-read behavior.
- Compatibility window and deletion date for legacy projections.

## Risks and guardrails

**Over-consolidation risk:** a generic request, result, graph, or artifact super-schema would reduce class count while increasing invalid states. Guardrail: share only where authority, lifecycle, and loss model match.

**Under-consolidation risk:** repeated validators and hand-written schemas drift silently. Guardrail: generated schemas, parity fixtures, and one private algorithm per invariant.

**Migration risk:** persisted artifacts may outlive code versions. Guardrail: explicit registered versions, deterministic normalization, compatibility fixtures, and no silent lossy conversion.

**Graph-coupling risk:** sharing a node type could make roadmap edits change execution identity or PR layout. Guardrail: share only graph mechanics and preserve domain namespaces.

**Manifest-bloat risk:** copying every referenced artifact makes the manifest an accidental universal schema. Guardrail: reference authorities and retain only bounded, reproducible indexes.

## Related architecture

- [Workflow contract map](./workflow-contract-map.md)
- [Skill Python bundle doctrine](./skill-python-bundle-doctrine.md)
- [CurdPlan authority ADR](../adr/workflow-contract-milknado-seam-001.md)
- [Writer-view boundary ADR](../adr/workflow-contract-milknado-seam-002.md)
- [Planner ownership ADR](../adr/workflow-contract-milknado-seam-003.md)
- [Executor result ADR](../adr/workflow-contract-milknado-seam-004.md)
- [Wheypoint continuity ADR](../adr/wheypoint-continuity-kernel-001.md)
- [Spec-format enforcement ADR](../adr/spec-format-enforcement-001.md)

[^1]: src/easy_cheese_schemas/**/*.py; repository-wide attrs model and enum inventory, verified 2026-08-29.
[^2]: /home/paul/Dev/milknado/src/milknado/domains/wiki/model.py:19-236; /home/paul/Dev/milknado/docs/adr/formalize-roadmap-graph-schema-001.md:5-20.
[^3]: src/easy_cheese_schemas/contracts.py:40-106; src/easy_cheese_schemas/schema_runtime.py:60-83,597-727.
[^4]: src/easy_cheese_schemas/contracts.py:502-705,844-890,1041-1060,1203-1216.
[^5]: .hallouminate/wiki/adr/workflow-contract-milknado-seam-003.md:12-20; .hallouminate/wiki/adr/workflow-contract-milknado-seam-004.md:12-18.
[^6]: .hallouminate/wiki/adr/workflow-contract-milknado-seam-001.md:12-20; src/easy_cheese_schemas/projections.py:93-202.
[^7]: src/easy_cheese_schemas/contracts.py:2095-2321; src/easy_cheese_schemas/gates.py:234-328; src/easy_cheese/shared/taste_test.py:68-188.
[^8]: src/easy_cheese_schemas/gates.py:234-328; src/easy_cheese/shared/taste_test.py:68-188.
[^9]: src/easy_cheese_schemas/manifest.py:290-487; src/easy_cheese/shared/fanout/validate_manifest.py:422-480.
[^10]: src/easy_cheese_schemas/wheypoint.py:251-666; .hallouminate/wiki/adr/wheypoint-continuity-kernel-001.md:3-14.
[^11]: src/easy_cheese_schemas/contracts.py:546-575; .hallouminate/wiki/adr/workflow-contract-milknado-seam-002.md:14-20.
[^12]: src/easy_cheese_schemas/artifacts.py:48-118; src/easy_cheese/shared/write_handoff_artifact.py:98-165.
[^13]: src/easy_cheese_schemas/contracts.py:1614-2083; src/easy_cheese_schemas/schema_runtime.py:793-1201; .hallouminate/wiki/adr/workflow-contract-milknado-seam-002.md:12-20.
[^14]: src/easy_cheese_schemas/contracts.py:1577-1604; src/easy_cheese_schemas/phase_contracts.py:120-179; src/easy_cheese_schemas/_phase_registry_compiler.py:128-349.
[^15]: src/easy_cheese_schemas/pr_plan.py:28-137; skills/ultracook/references/pr-plan-schema.json:5-63; src/easy_cheese/shared/fanout/validate_pr_plan.py:23-45; src/easy_cheese/shared/fanout/pr_plan_to_branches.py:54-97; skills/plate/SKILL.md:87-98; src/easy_cheese/skills/plate/publication.py:127-133.
[^16]: src/easy_cheese_schemas/schema_runtime.py:673-727; .hallouminate/wiki/adr/writer-view-boundary-simplification-001.md:10-23.
[^17]: src/easy_cheese_schemas/contracts.py:2095-2321; src/easy_cheese/skills/mold/validate_spec.py:132-334.
[^18]: src/easy_cheese_schemas/contracts.py:1041-1200; src/easy_cheese_schemas/workflow.py:666-946.
[^19]: .hallouminate/wiki/architecture/workflow-contract-map.md:57-79; repository-wide symbol search under src/ and skills/, verified 2026-08-29.
[^20]: src/easy_cheese_schemas/_document_rules_compiler.py:16-69; scripts/render_generated_regions.py:117-149,219-242; src/easy_cheese/shared/document_rules.py:1-43; src/easy_cheese/skills/mold/validate_spec.py:132-334.
[^21]: /home/paul/Dev/milknado/src/milknado/domains/wiki/model.py:19-236; /home/paul/Dev/milknado/docs/adr/formalize-roadmap-graph-schema-002.md:5-20.
[^22]: AGENTS.md: Single Quality Gate.
