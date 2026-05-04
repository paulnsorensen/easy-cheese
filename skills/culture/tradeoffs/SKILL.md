---
name: tradeoffs
description: Explore options and likely blast radius.
license: MIT
---

# /culture/tradeoffs

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Explore options and likely blast radius.

## Inputs

The current conversation and any user-stated constraints.

## Instructions

1. Compare options against the criteria.
2. Map likely blast radius and reversible decisions.
3. Avoid prematurely selecting an implementation.

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
