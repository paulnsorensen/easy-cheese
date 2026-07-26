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
2. Prepare the dataset and initial run together under `.context/`: `just distill-pilot --report <report.json> --adversarial-controls <controls.yaml> --out .context/distill/dataset.json --run .context/distill/run.json --run-id <id>`.
3. Record the human labels with `freeze-human-labels --run .context/distill/run.json --labels <human.yaml> --frozen-at <timestamp>`, then export only source spans with `export-llm-pairs --run ... --dataset .context/distill/dataset.json --out .context/distill/llm-pairs.json`.
4. Run the source-only LLM annotation as the agent. Do not expose the human labels or digest. Record its result with `record-llm-labels`, then run `reconcile` with the human, LLM, and second-human adjudication files. The run and annotations advance in one atomic write.
5. Run `score` directly as the agent with an explicit local adapter module, three immutable lock/snapshot pairs, the frozen fusion profile, and dependency inventory. Never invoke scoring, the current harness, or an LLM through `just` or CI. Missing or drifted evidence halts before `scores-v1` is written; no downloader or remote fallback exists.
6. Run `validate`, then give `propose --scores .context/distill/scores.json` agent-authored family drafts containing the canonical center, explicit residuals, both token-measured variants, original obligations, and recorded gate evidence. Proposal generation rejects missing pair coverage, mixed scorer profiles, or incomplete Arctic-S/BGE/NLI evidence. Generated datasets, run records, exports, scores, validation reports, diagnostics, and proposals must stay under `.context/`.
7. Run deterministic mutations, two original current-harness matrices, one matrix per representation, and the fresh-context diagnostic as agent-owned steps. A `concern` or `abstain` requires a separate human-authored `human-disposition-v1` record bound to the exact proposal digest; a draft field never counts as approval, and no disposition can waive deterministic, behavior, token, or overlap failures.
8. Run `apply --proposal <.context proposal> --repository <repo> --gate-contract <.context gate.json> [--disposition <.context disposition.json>]` one passing family at a time. Proposal load events must name every changed path and digest the exact old and new UTF-8 bytes. The three non-LLM gates run against an isolated applied-tree mirror; the real checkout changes atomically only after they pass. Finish with `verify --run <run.json> --evidence <interaction.json>` only after the agent-owned cross-family gate has passed and any interacting families have been bisected and reverted.

## Finish

Run `just check`. Preserve `.agents/skills/distill/` in repository history and confirm `scripts/stage_release.py` still stages only the published allowlist.
