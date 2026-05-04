---
name: restate
description: Restate the question or tension.
license: MIT
---

# /culture/restate

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Restate the question or tension.

## Inputs

The current conversation and any user-stated constraints.

## Instructions

1. Echo the question in one sentence.
2. Name the decision or tension being explored.
3. Confirm that no files will be changed.

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
