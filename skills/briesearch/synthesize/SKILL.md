---
name: synthesize
description: Merge findings, conflicts, caveats, and confidence.
license: MIT
---

# /briesearch/synthesize

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Merge findings, conflicts, caveats, and confidence.

## Inputs

The user prompt plus any assumptions carried forward from earlier briesearch sub-skills.

## Instructions

1. Merge overlapping findings into a concise answer.
2. Call out conflicts and caveats explicitly.
3. Assign qualitative confidence based on source quality and coverage.

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
