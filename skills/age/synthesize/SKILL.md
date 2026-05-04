---
name: synthesize
description: Group observations by stake and produce the report.
license: MIT
---

# /age/synthesize

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Group observations by stake and produce the report.

## Inputs

A diff/ref/path scope plus orientation evidence from `/age/orient`.

## Instructions

1. Merge dimension outputs by stake and location.
2. Highlight loci where multiple dimensions agree.
3. Produce the final report and `/cure` handoff candidates.

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
