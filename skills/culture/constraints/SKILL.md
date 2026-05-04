---
name: constraints
description: Identify assumptions, constraints, and decision criteria.
license: MIT
---

# /culture/constraints

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Identify assumptions, constraints, and decision criteria.

## Inputs

The current conversation and any user-stated constraints.

## Instructions

1. List known assumptions and constraints.
2. Ask about missing constraints only when necessary.
3. Separate facts from guesses.

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
