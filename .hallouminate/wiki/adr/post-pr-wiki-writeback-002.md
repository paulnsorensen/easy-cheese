# ADR: post-PR learnings write-back reuses wiki-ingest, not the personal wiki-curator skill

**Status:** accepted (2026-07-14)

The pipeline captures rationale only at design/fix time — curdle (design-time ADRs + model)
and `cure` step 6 (diff-touched domain-model correction, no ADRs — `skills/cure/SKILL.md:43`).
Implementation-time learnings (constraints found in `/cook`, findings from `/age`) are never
written back after the PR opens. A post-PR write-back needs a writer; two candidates were
compared plus inlining.

## Decision

Dispatch **`wiki-ingest`** (the hallouminate plugin skill, 0.2.2) detect-and-degrade at the
ship/handoff boundary. It is purpose-built for "fold new knowledge into an existing wiki /
record this decision", with dedup/route/merge/contradiction handling and opus-plan + haiku
fan-out — exactly the semantics the post-PR write-back needs, and it only adds learnings new
since curdle.

## Alternatives

- **`wiki-curator`** — rejected: it is a *personal dotfiles* skill scoped to
  `repo:dotfiles:wiki`; it would not exist in a consumer repo running easy-cheese. It has
  three portable authoring-hygiene capabilities `wiki-ingest` lacks (external-URL verify,
  worktree-safe write, `[[wikilink]]` convention) — those are being ported into `wiki-ingest`
  via **hallouminate#246** rather than depending on the personal skill.
- **Inline the write logic into `cure`** — rejected: duplicates dedup/route/merge logic that
  `wiki-ingest` already owns; the wiki writer belongs to hallouminate, not the pipeline.

## Consequences

Buys: easy-cheese depends only on the portable hallouminate plugin, degrading to a file
fallback when absent. Costs: `wiki-ingest` lacks URL-verify until #246 lands — acceptable,
since post-PR ADRs cite `file:line`/commits, not external URLs.
