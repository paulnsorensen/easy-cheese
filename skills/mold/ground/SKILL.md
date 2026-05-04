---
name: ground
description: Verify load-bearing claims with evidence.
license: MIT
---

# /mold/ground

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Verify load-bearing claims with evidence.

## Inputs

The current mold conversation state and any evidence gathered so far.

## Instructions

1. Identify claims that affect the spec.
2. Check code, docs, or `/briesearch` evidence for those claims.
3. Mark unresolved claims as `[?]`, `[TBD]`, or `[BLOCKED]`.

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
