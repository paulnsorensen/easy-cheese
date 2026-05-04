---
name: approval
description: Run the approval gate for artifact type, slug, and path.
license: MIT
---

# /mold/approval

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Run the approval gate for artifact type, slug, and path.

## Inputs

The current mold conversation state and any evidence gathered so far.

## Instructions

1. Present the approval checklist.
2. Ask for artifact type, slug, and target paths.
3. Do not proceed until the user approves or explicitly waives missing items.

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
