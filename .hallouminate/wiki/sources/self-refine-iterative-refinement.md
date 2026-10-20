# Self-Refine: Iterative Refinement with Self-Feedback

Aman Madaan and co-authors' research paper (arXiv 2303.17651, 2023), last verified 2026-10-17, supports the claim that an LLM that critiques and refines its own output improved task performance by about 20% absolute on average across seven evaluated tasks.
Canonical source: [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)

## Self-Refine result

In Self-Refine, "the same LLMs provides feedback for its output and uses it to refine itself, iteratively" (source L15-16). The authors evaluate it "across 7 diverse tasks" and report "improving by ~20% absolute on average in task performance" (L17).

## Limits of the Self-Refine evidence

The gain applies to the paper's seven tasks and metrics. It does not establish that open-ended coding loops improve architecture, maintainability, or live behavior. Compare with [llms-cannot-self-correct-reasoning-yet](./llms-cannot-self-correct-reasoning-yet.md), which finds that intrinsic self-correction can degrade reasoning.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://arxiv.org/abs/2303.17651 · Updated: 2026-10-18_
