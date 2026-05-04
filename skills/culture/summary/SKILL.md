---
name: summary
description: End with shared understanding and next step.
license: MIT
---

# /culture/summary

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

End with shared understanding and next step.

## Inputs

The current conversation and any user-stated constraints.

## Instructions

1. Summarize the shared mental model.
2. List open questions.
3. Suggest `/mold`, `/cook`, `/briesearch`, `/age`, or pause.

## Tool use

| Need | Prefer | Fallback |
| --- | --- | --- |
| Code orientation | Serena or LSP, `sg` | `ripgrep`, `find`, targeted reads |
| Diffs or examples | `delta` | plain `git diff` or targeted file reads |

Say once when a preferred tool is unavailable, use the fallback, and mention any evidence or precision loss that affects confidence.

## Output

A conversational update or final summary.

## Rules

- Keep tool use light.
- Do not mutate project state.
