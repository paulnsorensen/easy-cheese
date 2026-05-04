---
name: mode-route
description: Pick the starting mode from the user input.
license: MIT
---

# /mold/mode-route

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Pick the starting mode from the user input.

## Inputs

The current mold conversation state and any evidence gathered so far.

## Instructions

1. Classify the input as Explore, Ground, Shape, Sketch, Grill, or Diagnose.
2. Announce the selected mode in one line.
3. Switch modes only when the dialogue reveals a better fit.

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
