# Domain model

The skill-distillation domain separates evidence, adjudication, proposals, execution, and diagnostics so no similarity model or LLM result can authorize a rewrite by itself.[^1]

## Semantic skill distillation

### DistillationRun

One prepare, score, annotate, propose, rewrite, and final-verification execution. It binds source-report, preprocessing, model, fusion, fixture, harness, and result digests.

### DistillationFamily

A set of passages independently validated against the same `CanonicalCenter`. Membership is explicit and never inferred transitively.

### CanonicalCenter

The shared canonical clauses for a family plus the contract that each member's explicit residual preserves its original obligations.

### RelationAdjudication

The human resolution of relation or atom disagreements. It is required for every disagreement and every compression-positive pair.

### ObligationAtom

A signed behavioral statement with category, polarity, action, object, condition, order, and exact source span. Categories include triggers, routing, tools, writes, fallbacks, halts, artifacts, output fields, verification, and prohibitions.

### SemanticRelation

One of `equivalent`, `left-subsumes-right`, `right-subsumes-left`, `shared-shell`, `conflict`, `unrelated`, or `insufficient-evidence`. Only `equivalent` and `shared-shell` permit rewrite proposals.

### ModelLock

The pinned model artifact, revision, hash, runtime, and mode identity. Any mismatch halts scoring and proposal generation.

### FusionProfile

The BGE mode weights, candidate cutoff, training digest, recall floor, and held-out evaluation identity. It is frozen independently from `ModelLock`.

### BehaviorHarness

The fixed scenarios, current harness identity, model identity, three phrasings, repeated runs, fixtures, and results used to compare original and compact variants.

### DiagnosticDisposition

The human disposition of a fresh-context LLM result: `pass`, `concern`, or `abstain`. A concern or abstention blocks the family until disposition, and no disposition can waive a deterministic failure.

### RepresentationVariant

Either a physical-reference or compact-inline rendering of a family. The lower invocation-loaded token count may proceed only if every behavior gate passes.

### TokenizerIdentity

The current behavior-model tokenizer artifact, revision, hash, runtime, and encoding options. Exact UTF-8 events are encoded independently without chat templates or added special tokens; the identity digest excludes load events.

### TokenMetricProfile

A `TokenizerIdentity` digest plus ordered invocation load events. Event counts sum directly, so repeated loads remain repeated cost.

### BehaviorScorecard

One boolean obligation outcome with matrix identity, subject, scenario, phrasing, and repetition. Per scenario, two original matrices establish the baseline and one matrix evaluates each representation variant. A fixture with no non-critical assertions has a null non-critical rate.

### Blind-label commitment

The human-label file digest and timestamp frozen into a `DistillationRun` before source-only LLM export. `reconcile` verifies both committed digests and atomically advances `llm-recorded` to `reconciled`.

### DependencyInventoryV1

The sidecar and model-runtime dependency set frozen with package metadata in wave one. Later scoring curds consume it without changing `pyproject.toml` or `uv.lock`.

See [Semantic skill distillation](./semantic-skill-distillation.md) and [ADR: Evidence-gated semantic skill distillation](./adr/semantic-skill-distillation-001.md).

## Workflow continuity

The workflow-continuity model distinguishes a user's durable work item from branch/worktree executions, queued phase directives, and evidence passed between phases. The approved contract is [Cross-skill work contract](./specs/cross-skill-work-contract.md).

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

[^1]: `/Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/semantic-skill-distillation.md`.
