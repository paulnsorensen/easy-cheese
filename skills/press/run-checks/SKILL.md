---
name: run-checks
description: Run relevant existing checks.
license: MIT
---

# /press/run-checks

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Run relevant existing checks.

## Inputs

The cooked diff, spec or acceptance criteria, and test results from `/cook`.

## Instructions

1. Run the narrowest relevant tests.
2. Run wider existing gates when appropriate.
3. Record skipped checks with reasons.

## Tool use

| Need | Prefer | Fallback |
| --- | --- | --- |
| Code orientation | Serena or LSP, `sg` | `ripgrep`, `find`, targeted reads |
| Precise reads/edits | tilth read/edit | harness read/edit tools or patch application |
| Coverage/blast radius | code review graph, Serena or LSP | caller/import searches and test references |
| Tests | package scripts or documented commands | direct narrow test commands |

Say once when a preferred tool is unavailable, use the fallback, and mention any evidence or precision loss that affects confidence.

## Output

Press phase findings or final Press Report.

## Rules

- Do not edit outside the cooked scope.
- Preserve or strengthen assertions only.
