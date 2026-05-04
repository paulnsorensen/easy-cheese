---
name: seams
description: Sketch public seams before writing a spec.
license: MIT
---

# /mold/seams

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Sketch public seams before writing a spec.

## Inputs

The current mold conversation state and any evidence gathered so far.

## Instructions

1. Name affected modules, APIs, files, commands, or user-visible boundaries.
2. Sketch responsibilities in pseudocode or prose.
3. Confirm the seams are stable enough for a spec.

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
