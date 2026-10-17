# ADR: Both frames get the concurrent repair pathway; worktree primitive becomes shared  [status: accepted]

Spec: baseline-repair-pathway (durable specs corpus). Implements GitHub issue #304 (baseline-quality-gate-F001).

- **Context:** The repair pathway for recorded identical-to-baseline failures needs an isolated worktree running `/pasteurize` concurrently with the cook. Ultracook already owns worktree create/harvest/teardown primitives (`skills/ultracook/SKILL.md:175-181`); bare `/cook` has zero standing worktree infrastructure — only a throwaway checkout/stash for baseline capture.
- **Decision:** Both frames (`/ultracook` and bare `/cook`) get the full concurrent pathway. The worktree primitive is promoted from ultracook-internal to shared machinery callable by cook.
- **Alternatives:** Ultracook-only (smallest blast radius, machinery already in place); a degraded bare-cook form offering a follow-up `/pasteurize` at the handoff gate instead of concurrency. User explicitly chose full parity.
- **Consequences:** Bare-cook users get real concurrent repair, at the cost of moving the worktree floor into shared scripts and re-exporting it from both bundles; the repair worktree becomes the third worktree-consuming actor (after seed and curds) with its own lifecycle, excluded from run teardown.
