---
name: orient
description: Identify diff, scope, and relevant spec or issue.
license: MIT
---

# /age/orient

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Identify diff, scope, and relevant spec or issue.

## Inputs

A diff/ref/path scope plus orientation evidence from `/age/orient`.

## Instructions

1. Identify the ref, range, or working diff.
2. Identify the requested path scope.
3. Find any spec, issue, tests, or PR context that define intent.

## Tool use

| Need | Prefer | Fallback |
| --- | --- | --- |
| Code orientation | Serena or LSP, `sg` | `ripgrep`, `find`, targeted reads |
| Precise reads/edits | tilth read/edit | harness read/edit tools or patch application |
| Diff inspection | `delta` | `git diff --unified=3` |
| GitHub/PR context | `gh` or GitHub integration | local git commands or user-provided PR data |

Say once when a preferred tool is unavailable, use the fallback, and mention any evidence or precision loss that affects confidence.

## Output

Dimension findings with stake, evidence, recommendation, or `scope_match: false`.

## Rules

- Do not edit files.
- Keep confidence qualitative.
- Limit findings to evidence from the scoped diff.
