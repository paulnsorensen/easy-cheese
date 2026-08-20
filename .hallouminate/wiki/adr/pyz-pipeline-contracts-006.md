# ADR: The Astro site source moves out of src/ to website/, leaving src/ Python sources plus docs

Status: accepted (2026-08-18)

Spec: pyz-pipeline-contracts (durable specs corpus).

## Context

Astro's default srcDir made src/ simultaneously the docs-site source tree and the Python source tree — the root cause of layout confusion.

## Decision

Move components/, pages/, styles/, content/, sidebar.mjs, content.config.ts to website/ via the srcDir config key; gen_docs.py, the docs workflow, and tests/js follow. A src-layout test permits Python sources plus `PYTHON_SCRIPTS.md` and `README.md`, and rejects Astro/site sources or config under `src/`. Rejected: moving Python out (60+ file moves) and nesting both (maximum churn).

## Consequences

src/ matches the universal convention; the smallest-diff restructure wins.
