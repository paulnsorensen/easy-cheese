# Building effective agents

Anthropic's engineering article (December 2024), last verified 2026-10-17, supports the claim that an evaluator-optimizer loop fits tasks with clear evaluation criteria and measurable refinement, and needs environment ground truth and stopping conditions.
Canonical source: [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)

## Evaluator-optimizer loop

The Anthropic agents article describes the evaluator-optimizer workflow: "one LLM call generates a response while another provides evaluation and feedback in a loop" (source L104). It is "particularly effective when we have clear evaluation criteria, and when iterative refinement provides measurable value" (L107).

## Ground truth and stopping conditions

The article says agents need "ground truth from the environment at each step (such as tool call results or code execution)" and "stopping conditions (such as a maximum number of iterations)" (L114).

## Limits of the agents-article evidence

The article gives pattern advice. It is not a controlled comparison of loop and one-pass coding workflows.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://www.anthropic.com/engineering/building-effective-agents · Updated: 2026-10-18_
