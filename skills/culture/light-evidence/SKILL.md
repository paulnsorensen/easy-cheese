---
name: light-evidence
description: Use light evidence without turning into deep research.
license: MIT
---

# /culture/light-evidence

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Use light evidence without turning into deep research.

## Inputs

The current conversation and any user-stated constraints.

## Instructions

1. Use quick code or doc checks only when they clarify discussion.
2. Route deep external research to `/briesearch`.
3. Mark unsupported claims as assumptions.

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
