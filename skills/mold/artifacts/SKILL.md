---
name: artifacts
description: Write only the approved spec or issue drafts.
license: MIT
---

# /mold/artifacts

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Write only the approved spec or issue drafts.

## Inputs

The current mold conversation state and any evidence gathered so far.

## Instructions

1. Write only the approved artifacts.
2. Separate spec requirements from parking-lot issues.
3. Suggest `/cook` only after the artifact is ready.

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
