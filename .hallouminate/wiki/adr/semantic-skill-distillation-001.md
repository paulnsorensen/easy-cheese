# ADR: Evidence-gated semantic skill distillation

**Status:** Accepted

**Date:** 2026-07-26

## Context

The overlap ratchet can identify likely repeated passages, but similarity alone cannot justify rewriting policy-bearing skill prose. A rewrite may reduce static text while preserving or increasing invocation-loaded tokens, or it may silently change approvals, routing, writes, halts, tool order, and durable output contracts.[^1]

The pilot needs stronger semantic models without allowing model output to become ground truth or introducing model downloads and LLM variability into CI.

## Decision

Build a separate Python `skill-distill` sidecar that consumes the existing Rust overlap report JSON. Keep the Rust report, calibration, and baseline schemas unchanged.[^2]

The sidecar will:

- preserve Arctic-S as a frozen historical control;
- evaluate full BGE-M3 dense, sparse, and multi-vector retrieval;
- use bidirectional DeBERTa-v3-base NLI only as a diagnostic;
- make reconciled human relations and signed obligation atoms authoritative;
- permit rewrites only for `equivalent` and `shared-shell` families;
- validate each member against one canonical center and explicit residual instead of using transitive components;
- optimize invocation-loaded tokens rather than static file size;
- require deterministic mutation tests, repeated current-harness behavior checks, and a fresh-context LLM diagnostic;
- apply and revert rewrites as family-atomic transactions, followed by a cross-family interaction gate.

The experimental `/distill` orchestrator will be tracked under `.agents/skills/distill/` but excluded from the published skill bundle. Model-free tests will join `just check`; local pinned model evaluation will run through `just distill-pilot`; LLM diagnostics will remain outside `just` and CI.[^1]



### Deterministic locks

The primary token metric separates pinned tokenizer identity and encoding options from independently counted load events; duplicate loads remain duplicate cost. Behavior comparison runs two original 3-by-3 matrices and one variant 3-by-3 matrix per scenario, with explicit handling for fixtures that contain no non-critical assertions.

BGE fusion records deterministic split/fold seeds and sparse-stratum rules. Each weight tuple selects its smallest qualifying candidate cutoff before tuples compare recall, MRR, and lexicographic weights. Annotation enforces atomic `prepared -> human-frozen -> llm-recorded -> reconciled` transitions. Wave one freezes all scorer dependencies before parallel scoring work begins.

## Alternatives considered

### Extend the Rust overlap analyzer

Rejected for the pilot. The existing analyzer is a deterministic overlap and ratchet tool; adding model runtimes, human annotation, proposals, and rewrite transactions would mix distinct responsibilities and force report-schema changes.

### Replace Arctic-S with one stronger embedding model

Rejected. Keeping Arctic-S provides historical comparability, while BGE-M3 tests a distinct hybrid-retrieval hypothesis. Qwen3 and Nomic remain outside this pilot.

### Use NLI or an LLM as semantic authority

Rejected. Imperative policy prose does not map reliably enough to declarative entailment, and LLM agreement is not proof. Both remain evidence sources subordinate to reconciled human labels and deterministic obligations.

### Canonicalize connected components

Rejected. Pairwise similarity is not transitive. Each member must prove equivalence to the same canonical center with its own residual.

### Put the LLM gate in CI

Rejected. Provider behavior is not sufficiently hermetic for the normal quality gate. Cross-provider and hermetic keyed runs are a separate follow-up.

## Consequences

The pilot adds a second tool and annotation workflow, but protects the current analyzer's stable contract. It favors false negatives over destructive compression and requires human effort for disagreements and all compression-positive pairs. Model and runtime drift invalidate evidence rather than degrading silently. Successful families reduce real invocation cost; failed families can be reversed independently.

See [Semantic skill distillation](../semantic-skill-distillation.md) for the protocol and [Domain model](../domain-model.md) for the vocabulary.

[^1]: `/Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/semantic-skill-distillation.md`.
[^2]: `tools/skill-overlap/src/main.rs:134-147,277-321`.