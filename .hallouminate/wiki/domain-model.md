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

[^1]: `/Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/semantic-skill-distillation.md`.