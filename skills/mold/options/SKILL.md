---
name: options
description: Compare viable options and non-goals.
license: MIT
---

# /mold/options

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Compare viable options and non-goals.

## Inputs

The current mold conversation state and any evidence gathered so far.

## Instructions

1. List viable options including Do Nothing when relevant.
2. Compare trade-offs against stated criteria.
3. Choose or recommend one option with non-goals.

## Tool use

| Need | Prefer | Fallback |
| --- | --- | --- |
| Code orientation | Serena or LSP, `sg` | `ripgrep`, `find`, targeted reads |
| Precise reads/edits | tilth read/edit | harness read/edit tools or patch application |
| Current web facts | Tavily | generic web search or user-provided sources |
| Library/API docs | Context7 | repo docs, package docs, vendor pages |

Say once when a preferred tool is unavailable, use the fallback, and mention any evidence or precision loss that affects confidence.

## Output

Updated understanding, approval status, or written artifact summary as appropriate.

## Rules

- Preserve unresolved questions.
- Do not silently settle uncertain claims.
