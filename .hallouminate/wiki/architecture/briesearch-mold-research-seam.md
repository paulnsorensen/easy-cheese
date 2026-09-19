# Briesearch and Mold research seam

The Briesearch and Mold research seam is the path from a research slug to a finalized Mold spec and its consumer-valid Cook handoff: Briesearch writes research, Mold consumes it, and Mold's finalizer publishes the canonical pointer for Cook. The r014 edge reviews (`edge-briesearch-mold.md`, `edge-mold-briesearch.md`, `edge-cheese-mold.md`, `edge-mold-cook.md`, `edge-schemas-mold.md`) recorded the seam rules below. Spec discovery fallbacks are in [cheese-corpus-setup-002](../adr/cheese-corpus-setup-002.md).

## Research slugs and paths

`ResearchLayout` enforces four to six kebab-case words. It returns absolute operational paths and a corpus-relative `artifact` storage identity.[^1] Reports live at `research/<slug>/<slug>.md`, with the slug derived from the parent mini-spec slug. A durable document that links the separately stored report records the full absolute `report` path. It does not copy the report or record the corpus-relative storage identity.[^2]

[^1]: src/easy_cheese/skills/briesearch/research_layout.py:32-78
[^2]: skills/mold/references/mini-spec-mode.md:71-98; skills/briesearch/references/synthesis.md:112-116

## Internal callers set `invocation: sidechain`

The ledger parser (`src/easy_cheese/skills/briesearch/ledger.py:329-337`) defaults a missing `invocation` to `top-level`. A skill that dispatches Briesearch internally must send `invocation: sidechain` or its run is indistinguishable from a user-facing run (`skills/briesearch/references/context-isolation.md:41-65`).

## Ledger URLs are redacted

Never persist a credential-bearing URL. Canonical identity comes from hostname and port only; diagnostics go through `render_url`; a non-root trailing slash is significant (`/a` differs from `/a/`); citation parsing balances parentheses.

## Spec inputs and finalizer output

`artifact-path specs <slug>` resolves the durable Mold spec input under the XDG corpus (`src/easy_cheese/shared/paths.py:252-284`). The resolved path is supplied to Mold's finalizer; it is not a direct Cook handoff. Validate every user-supplied slug with `validate_slug` before it enters a path.

## The finalizer is the Mold-to-Cook boundary

`python3 skills/mold/scripts/mold.pyz finalize` is the single Mold publication path. It validates the bounded spec and readiness evidence, publishes the referenced artifacts, and reveals the canonical `HandoffPointer` under `pointers/<operation-id>.json`. Cook consumes that pointer through the shared handoff validator, which resolves and digest-checks the references, approval, and landing before readiness. Cook no longer performs the removed optional-spec landing lookup or emits its legacy stderr note.

## Grounding rows must be real

The Mold document schema requires one Grounding row per probe (`wiki`, `explorer`) with non-empty evidence of an attempted action (`src/easy_cheese_schemas/contracts.py:2338-2356,2487-2617`). `validate_spec.py:447-514` and `taste_test.py:662-802` fabricated two `unavailable` rows plus default frontmatter when a document, especially a mini-spec, omitted the section, so strict validation returned `0` for a document that never met the contract. Mini-spec mode is not gated by `validate_spec.py`; whether it needs grounding is unresolved.

## One document validator

Mold invariants existed three times: `contracts.py`, `validate_spec.py`, and `taste_test.py`. The direction is to parse once into `MoldSpecDocument` and reuse it; `taste_test` still parses on its own. The standalone validator falls back to the stdlib path on any import failure, because `compat.py` can fail on `cattrs` before `attrs`.

## Wiki corpus selection is exact

A grounding tool with several global corpora must match the corpus to the current repository or use the workspace default. A first-match fallback copies private rationale across repositories; record ambiguity as `unavailable`.

_Source: r014 skill-review round notes (ingest hash 499c49c7b67d5eb6), verified against `research_layout.py` on 2026-09-04 · Updated: 2026-09-18 · Supersedes: the former publish/direct-spec handoff route and the review-time claim that slug word count was unenforced_
