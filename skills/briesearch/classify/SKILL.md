---
name: classify
description: Classify the research question and missing context.
license: MIT
---

# /briesearch/classify

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Classify the research question and missing context.

## Inputs

The user prompt plus any assumptions carried forward from earlier briesearch sub-skills.

## Instructions

1. Read the full prompt as the research question.
2. Identify whether this is library docs, current web facts, codebase pattern, GitHub example, comparison, or best practice.
3. Ask one clarifying question only when version, scope, or decision criteria materially changes the search.

## Tool use

| Need | Prefer | Fallback |
| --- | --- | --- |
| Current web facts | Tavily | generic web search or user-provided sources |
| Library/API docs | Context7 | repo docs, package docs, vendor pages |
| GitHub examples | `gh` or GitHub integration | web search scoped to GitHub, or skip with confidence note |
| Local patterns | Serena or LSP, `sg`, tilth | `ripgrep`, `find`, targeted reads |

Say once when a preferred tool is unavailable, use the fallback, and mention any evidence or precision loss that affects confidence.

## Output

A concise research note, evidence bullets, confidence, and next step.

## Rules

- Cite or name evidence sources.
- Mark claims as unverified when evidence is weak.
