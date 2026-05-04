---
name: validate
description: Run relevant existing validation.
license: MIT
---

# /cure/validate

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Run relevant existing validation.

## Inputs

Selected review findings, CI failures, or scoped instructions plus any prior cure phase output.

## Instructions

1. Run narrow tests or checks that prove the fix.
2. Run wider existing gates when relevant.
3. Record failures and skipped checks honestly.

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
