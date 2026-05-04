---
name: gather
description: Collect only enough evidence to answer confidently.
license: MIT
---

# /briesearch/gather

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Collect only enough evidence to answer confidently.

## Inputs

The user prompt plus any assumptions carried forward from earlier briesearch sub-skills.

## Instructions

1. Query preferred sources in priority order, using fallbacks when needed.
2. Prefer primary docs and direct code evidence over secondary commentary.
3. Record source notes, conflicts, freshness, and uncertainty.

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
