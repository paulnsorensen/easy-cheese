# Briesearch and Mold research seam

The Briesearch and Mold research seam is the path from a research slug to a published spec: Briesearch writes research, Mold consumes it and writes the spec, and Cook accepts Mold's output through a pointer. The r014 edge reviews (`edge-briesearch-mold.md`, `edge-mold-briesearch.md`, `edge-cheese-mold.md`, `edge-mold-cook.md`, `edge-schemas-mold.md`) recorded the seam rules below. Spec discovery fallbacks are in [cheese-corpus-setup-002](../adr/cheese-corpus-setup-002.md).

## Research slugs and paths

`ResearchLayout` (`src/easy_cheese/skills/briesearch/research_layout.py:27-65`) enforces four to six kebab-case words and returns absolute `corpus_root`, `dir`, `report`, `raw_dir`, `manifest`, and `slug`. Reports live at `research/<slug>/<slug>.md`, with the slug derived from the parent mini-spec slug. Mold's `## Provenance` bullet expects a corpus-relative path (`skills/mold/references/mini-spec-mode.md:48-62`), so the caller converts before it writes. Before the r014 cure the CLI checked only kebab-case; the word count is now enforced.

## Internal callers set `invocation: sidechain`

The ledger parser (`src/easy_cheese/skills/briesearch/ledger.py:329-337`) defaults a missing `invocation` to `top-level`. A skill that dispatches Briesearch internally must send `invocation: sidechain` or its run is indistinguishable from a user-facing run (`skills/briesearch/references/context-isolation.md:41-65`).

## Ledger URLs are redacted

Never persist a credential-bearing URL. Canonical identity comes from hostname and port only; diagnostics go through `render_url`; a non-root trailing slash is significant (`/a` differs from `/a/`); citation parsing balances parentheses.

## Spec paths come from the resolver

Mold specs are not written to a literal `.cheese/specs/<slug>.md`. `artifact-path specs <slug>` and `validate-spec --strict <path>` resolve into the XDG durable corpus (`src/easy_cheese/shared/paths.py:252-284`). Callers use the returned path. The same bare slug resolves to different files by resolver: `artifact-path specs` gives `~/.local/share/cheese/<org-repo>/specs/<slug>.md`, while phase reports live under `.cheese/<skill>/`. Cook once resolved a Pasteurize slug as a spec and missed the `.cheese/pasteurize/` report; pick the resolver for the artifact kind. Validate every user-supplied slug with `validate_slug` before it enters a path (Curdle writes are the known case).

## Mold's normal path skips `publish`

The canonical Mold to Cook contract is `mold.pyz publish` writing a `HandoffPointer` under `pointers/<operation-id>.json`, then Cook `accept` validating route, receipt, and digest. Mold's taste-test flow emits `/cook --auto <spec_ref>` instead (`src/easy_cheese/shared/taste_test.py:1142-1186`, `skills/mold/SKILL.md:21-24,109,127-133`), so `accept` and its checks are skipped on the common path. A producer must invoke its publish step, not only validate.

## Grounding rows must be real

The Mold document schema requires one Grounding row per probe (`wiki`, `explorer`) with non-empty evidence of an attempted action (`src/easy_cheese_schemas/contracts.py:2338-2356,2487-2617`). `validate_spec.py:447-514` and `taste_test.py:662-802` fabricated two `unavailable` rows plus default frontmatter when a document, especially a mini-spec, omitted the section, so strict validation returned `0` for a document that never met the contract. Mini-spec mode is not gated by `validate_spec.py`; whether it needs grounding is unresolved.

## One document validator

Mold invariants existed three times: `contracts.py`, `validate_spec.py`, and `taste_test.py`. The direction is to parse once into `MoldSpecDocument` and reuse it; `taste_test` still parses on its own. The standalone validator falls back to the stdlib path on any import failure, because `compat.py` can fail on `cattrs` before `attrs`.

## Wiki corpus selection is exact

A grounding tool with several global corpora must match the corpus to the current repository or use the workspace default. A first-match fallback copies private rationale across repositories; record ambiguity as `unavailable`.

_Source: r014 skill-review round notes (ingest hash 499c49c7b67d5eb6), verified against `research_layout.py` on 2026-09-04 · Updated: 2026-09-04 · Supersedes: the review-time claim that slug word count was unenforced_
