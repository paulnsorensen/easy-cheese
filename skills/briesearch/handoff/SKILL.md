---
name: handoff
description: Stop after research and recommend the next skill or action.
license: MIT
---

# /briesearch/handoff

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Stop after research and recommend the next skill or action.

## Inputs

The user prompt plus any assumptions carried forward from earlier briesearch sub-skills.

## Instructions

1. Recommend the smallest next action or skill.
2. Stop at research boundaries.
3. Keep raw notes out of the response unless requested.

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
