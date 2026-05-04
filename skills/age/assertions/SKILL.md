---
name: assertions
description: Review weak tests, shallow existence checks, and swallowed errors.
license: MIT
---

# /age/assertions

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Review weak tests, shallow existence checks, and swallowed errors.

## Inputs

A diff/ref/path scope plus orientation evidence from `/age/orient`.

## Instructions

1. Review only the requested diff or scope for this dimension.
2. Cite file paths, line ranges, commands, or unavailable evidence notes.
3. Return no finding when the rubric does not apply.

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
