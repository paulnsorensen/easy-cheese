# Semantic skill distillation

Semantic skill distillation is an evidence-gated rewrite protocol: it may canonicalize only independently validated `equivalent` and `shared-shell` skill passages, and only when the resulting invocation loads fewer tokens without changing critical behavior.[^1]

## Why this exists

The overlap ratchet detects normalized equality and symmetric embedding similarity, but those signals do not distinguish equivalence, directional containment, shared shells, conflicts, or unrelated prose. They also cannot establish that routing, approvals, tool order, writes, halts, and artifacts survive a rewrite.[^2]

The distillation pilot therefore keeps similarity as candidate evidence and makes signed obligations plus behavioral evaluation the rewrite authority. This extends, rather than replaces, the existing overlap ratchet described in [Skill overlap ratchet](./adr/skill-overlap-ratchet-001.md).

## Protocol

1. Consume the existing Rust overlap report JSON without modifying its schemas.
2. Build a deterministic 421-pair pilot: all 181 block-band pairs, 200 stratified review-band pairs, and 40 adversarial pairs.
3. Score every labeled pair with frozen Arctic-S control evidence and full BGE-M3 dense, sparse, and multi-vector evidence.
4. Collect a blind human relation, an independent LLM relation and signed atoms, then reconcile disagreements; a second human adjudicates every disagreement and compression-positive pair.
5. Use bidirectional DeBERTa-v3-base NLI only as a diagnostic.
6. Form families around one canonical center; validate every member independently with an explicit residual. Never infer family membership transitively.
7. Compare physical-reference and compact-inline representations by invocation-loaded tokens, not static file size.
8. Run deterministic mutations, the current-harness behavior matrix, and a fresh-context LLM diagnostic.
9. Apply each passing family atomically, then run a cross-family interaction gate and bisect failures.

## Invariants

- Critical obligations allow zero distortion.
- Non-critical degradation cannot exceed original self-variance capped at five percentage points.
- `concern` and `abstain` from the LLM diagnostic require human disposition; the LLM cannot waive deterministic failures.
- Model artifact, revision, hash, runtime, or BGE-mode drift halts the run.
- Only `equivalent` and `shared-shell` relations are rewrite-eligible.
- Shared-shell residuals remain explicit.
- A family with zero or negative invocation-loaded token savings is ineligible.
- The LLM diagnostic never runs in CI or through `just`.



### Locked measurement and validation formulas

- `TokenizerIdentity` hashes the current behavior-model tokenizer artifact, revision, hash, runtime, and encoding options. Every exact UTF-8 load event is encoded independently with no chat template and no added special tokens, then summed. Recursive references count only when loaded; repeated loads count repeatedly.
- Behavior fixtures emit boolean `BehaviorScorecard` rows with scenario and matrix identity. Per scenario, two original 3-by-3 matrices establish the baseline and every variant gets one 3-by-3 matrix. A fixture without non-critical assertions records a null rate and runs only the critical gate.
- BGE fusion records fixed split and fold seeds. Sparse strata merge deterministically before stable-hash held-out assignment and round-robin development folds. Each weight tuple selects its smallest qualifying `k` from 1 through 50; eligible tuples compare recall, MRR, then lexicographic weights.
- Annotation enforces `prepared -> human-frozen -> llm-recorded -> reconciled`. `reconcile` requires the run, verifies both committed digests, and advances state atomically. Invalid order halts without mutation.

## Repository boundary

The deterministic sidecar lives under `tools/skill-distill/`. The experimental orchestrator lives under the repo-local `.agents/skills/distill/` and remains excluded from release staging. Model-free tests join `just check`; pinned local model evaluation runs separately through `just distill-pilot`; current-harness and LLM diagnostics remain agent-owned through `/distill`.[^1]

Human records, schemas, manifests, adversarial fixtures, gold labels, and adjudications are tracked. Vectors, raw scores, diagnostics, and proposals stay transient under `.context/`.



Wave one owns `pyproject.toml`, `uv.lock`, and `DependencyInventoryV1`; later scoring waves consume that frozen inventory without modifying package metadata.

## Apply-gate mirror: containment vs. recursion safety

`lifecycle.apply_proposal` copies the repository into a disposable temp mirror,
applies a proposed family's changes there, and runs the operator-supplied
post-write gate against the mirror instead of the real tree — pinned by
`test_failed_gate_cannot_mutate_real_unrelated_files`
(`tests/skill-distill/python/test_lifecycle.py`).

That mirror has two safety properties that a naive `shutil.copytree(symlinks=...)`
choice trades against each other, not two independent knobs:

- `symlinks=False` dereferences symlinks into regular files. A gate writing
  through a symlink stays contained inside the mirror, but a directory symlink
  pointing at an ancestor makes the copy recurse until disk or stack
  exhaustion.
- `symlinks=True` fixes the recursion but breaks containment — symlinks copy
  verbatim, so one with an absolute or repo-escaping target still points at
  the real filesystem, and a gate writing through it escapes the sandbox.

Neither value is correct alone. The fix keeps `symlinks=True` and adds a
post-copy pass, `_neutralize_escaping_symlinks`, that walks the mirror with
`os.walk(followlinks=False)`, resolves each symlink through its full chain,
and unlinks any whose resolved target lands outside the mirror root.

Two things not to assume from reading the code in isolation:

- `_has_symlink_component` guards *proposal change paths* — it says nothing
  about gate side effects, and does not cover this case.
- Accepted tradeoff: a legitimate repo symlink pointing to an absolute path
  outside the repo is now silently removed from the mirror, so a gate
  depending on such a link fails without an obvious cause.

The mirror also excludes `.git`, `.venv`, `node_modules`, and `__pycache__`
for copy cost. Because gate argv is arbitrary operator input, a gate
referencing an excluded path (e.g. `.venv/bin/pytest`) now surfaces as an
attributed gate failure rather than an uncaught `FileNotFoundError`
traceback.

_Source: PR 329 (commit 0d671e9) · Updated: 2026-07-26_

## Related decisions

- [ADR: Evidence-gated semantic skill distillation](./adr/semantic-skill-distillation-001.md)
- [Domain model](./domain-model.md)

[^1]: `/Users/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/semantic-skill-distillation.md`.
[^2]: `tools/skill-overlap/src/main.rs:277-321` and `.hallouminate/wiki/adr/skill-overlap-ratchet-001.md`.