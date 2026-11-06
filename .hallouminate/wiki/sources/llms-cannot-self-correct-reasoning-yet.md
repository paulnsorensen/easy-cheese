# Large Language Models Cannot Self-Correct Reasoning Yet

Jie Huang and co-authors' peer-reviewed conference paper (ICLR 2024), last verified 2026-10-17, supports the claim that LLMs struggle to self-correct reasoning without external feedback, and that performance can degrade after intrinsic self-correction.
Canonical source: [Large Language Models Cannot Self-Correct Reasoning Yet](https://proceedings.iclr.cc/paper_files/paper/2024/hash/8b4add8b0aa8749d80a34ca5d941c355-Abstract-Conference.html)

## Intrinsic self-correction result

The paper studies intrinsic self-correction, where "an LLM attempts to correct its initial responses based solely on its inherent capabilities, without the crutch of external feedback". In reasoning tasks, "at times, their performance even degrades after self-correction" (source L9-10).

## How easy-cheese research applies it

A model can suggest a repair. Its own confidence or explanation does not establish success. A repair loop needs an external, observable check.

## Limits of the self-correction evidence

The paper studies reasoning tasks, not code architecture or live software behavior.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://proceedings.iclr.cc/paper_files/paper/2024/hash/8b4add8b0aa8749d80a34ca5d941c355-Abstract-Conference.html · Updated: 2026-10-18_
