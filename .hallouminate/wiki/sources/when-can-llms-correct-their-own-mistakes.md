# When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs

Ryo Kamoi, Yusen Zhang, Nan Zhang, Jiawei Han, and Rui Zhang's peer-reviewed survey (TACL vol. 12, 2024), last verified 2026-10-17, supports the claim that LLM self-correction works well in tasks that can use reliable external feedback.
Canonical source: [When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs](https://aclanthology.org/2024.tacl-1.78/)

## Self-correction survey findings

The TACL self-correction survey finds that "prior studies often do not define their research questions in detail and involve impractical frameworks or unfair evaluations" (source L59). It concludes that "self-correction works well in tasks that can use reliable external feedback" (L60).

## How easy-cheese research applies it

The reliable external feedback for a coding agent is an executed check at the real boundary: a test result, a command output, or an inspected environment state. A loop without that signal relies on the model's own judgment.

## Limits of the survey evidence

Transfer from the surveyed tasks to this codebase is not measured.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://aclanthology.org/2024.tacl-1.78/ · Updated: 2026-10-18_
