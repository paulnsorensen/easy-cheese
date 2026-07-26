---
name: distill
description: Run the experimental, evidence-gated semantic skill-distillation pilot in easy-cheese. Use when preparing the locked overlap dataset, collecting blind relation labels, running pinned local semantic scoring, evaluating invocation-loaded token savings, or validating and applying a proposed skill rewrite.
---

# Distill

Run semantic skill distillation as an experimental repository-local protocol. This skill is tracked for pilot history but must not be copied into the published `skills/` bundle.

## Boundaries

- Treat reconciled human relations and signed obligation atoms as authority. Similarity, NLI, and LLM output are evidence only.
- Rewrite only `equivalent` and `shared-shell` families. Keep every shared-shell residual explicit and validate each member against one canonical center; do not infer membership transitively.
- Favor false negatives. Critical obligations permit zero distortion, and a family with no invocation-loaded token saving is ineligible.
- Keep vectors, raw scores, diagnostics, and proposals under `.context/`. Track only the specified records, schemas, manifests, fixtures, gold labels, and adjudications.

## Run the pilot

1. Run `just test-skill-distill`. Stop if the model-free contracts and deterministic algorithms fail.
2. Produce the Rust overlap report and adversarial-controls file without changing the overlap report schema.
3. Run `just distill-pilot --report <report.json> --adversarial-controls <controls.json> --out <dataset.json>` to prepare the deterministic dataset.
4. Freeze the human labels before obtaining independent LLM labels. Reconcile committed digests only in the enforced `prepared -> human-frozen -> llm-recorded -> reconciled` order; a second human adjudicates every disagreement and compression-positive pair.
5. Run scoring directly as the agent, never through `just` or CI. Require local, immutable locks for Arctic-S, full BGE-M3 dense/sparse/multi-vector evidence, and bidirectional DeBERTa-v3-base NLI. Verify artifact revision, artifact hash, runtime identity, dependency inventory, and BGE modes before loading anything. Do not download models; missing or drifted artifacts halt the run.
6. Compare physical-reference and compact-inline proposals by invocation-loaded tokens. Count every exact UTF-8 load event independently, including repeated loads, with the pinned behavior-model tokenizer and no chat template or added special tokens.
7. Run deterministic mutations, then the current-harness behavior matrix and fresh-context LLM diagnostic directly as agent-owned diagnostics. Never add either diagnostic to a `just` recipe or CI. `concern` and `abstain` require human disposition and cannot waive deterministic failures.
8. Apply a passing family atomically with its reversal patch, run the cross-family interaction gate, and bisect and revert any failure.

## Finish

Run `just check`. Preserve `.agents/skills/distill/` in repository history and confirm `scripts/stage_release.py` still stages only the published allowlist.
