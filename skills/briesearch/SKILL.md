---
name: briesearch
description: Research technical questions across docs, web, codebase, and GitHub examples with explicit source sub-skills.
license: MIT
---

# /briesearch

Source: adapted from `paulnsorensen/cheese-flow.git` while keeping this repository skills-only and portable.

## Use when

A technical question needs evidence before a decision: library behavior, vendor docs, implementation patterns, or comparable examples.

## Do not use when

The answer is a single obvious file lookup or the user already supplied enough evidence.

## Sub-skills

| Sub-skill | Purpose |
| --- | --- |
| `/briesearch/classify` | Classify the research question and missing context. |
| `/briesearch/source-plan` | Choose sources, preferred tools, and fallbacks before searching. |
| `/briesearch/gather` | Collect only enough evidence to answer confidently. |
| `/briesearch/synthesize` | Merge findings, conflicts, caveats, and confidence. |
| `/briesearch/handoff` | Stop after research and recommend the next skill or action. |

Default order: `/briesearch/classify` → `/briesearch/source-plan` → `/briesearch/gather` → `/briesearch/synthesize` → `/briesearch/handoff`

Run only the sub-skills needed for the user request, but do not skip a gate that protects correctness or user intent.

## Output

Return a compact answer with evidence, confidence, and the recommended next step.

## Rules

- Do not implement the result unless the user separately asks.
- Do not pretend an unavailable source was checked.
