---
name: apply
description: Apply approved fixes by the right handler.
license: MIT
---

# /cure/apply

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Apply approved fixes by the right handler.

## Inputs

Selected review findings, CI failures, or scoped instructions plus any prior cure phase output.

## Instructions

1. Apply one logical fix group at a time.
2. Use mechanical edits for anchored fixes and cook-style changes for judgment fixes.
3. Keep each fix scoped to the selected item.

## Tool use

| Need | Prefer | Fallback |
| --- | --- | --- |
| Code orientation | Serena or LSP, `sg` | `ripgrep`, `find`, targeted reads |
| Precise reads/edits | tilth read/edit | harness read/edit tools or patch application |
| Findings context | `/age` report plus code review graph | diff, touched files, tests, and searches |
| CI and PR context | `gh` or GitHub integration | local test output or user-provided logs |
| Diffs | `delta` | plain `git diff` |

Say once when a preferred tool is unavailable, use the fallback, and mention any evidence or precision loss that affects confidence.

## Output

A cure phase update or final Cure Report.

## Rules

- Never apply unselected findings.
- Stop if validation cannot prove the fix safely.
