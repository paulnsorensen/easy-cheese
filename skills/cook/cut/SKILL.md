---
name: cut
description: Create failing tests before production changes.
license: MIT
---

# /cook/cut

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Create failing tests before production changes.

## Inputs

An approved spec, pasted requirements, or focused request plus outputs from prior cook sub-skills.

## Instructions

1. Find existing tests and relevant patterns.
2. Add or update tests that fail for the expected reason.
3. Report changed test files, covered requirements, and observed red failures.

## Tool use

| Need | Prefer | Fallback |
| --- | --- | --- |
| Code orientation | Serena or LSP, `sg` | `ripgrep`, `find`, targeted reads |
| Precise reads/edits | tilth read/edit | harness read/edit tools or patch application |
| Tests and tasks | `just`, package scripts, documented commands | direct test/build commands already in the repo |
| Diffs | `delta` | plain `git diff` |

Say once when a preferred tool is unavailable, use the fallback, and mention any evidence or precision loss that affects confidence.

## Output

A phase report with files, checks, findings, and next action.

## Rules

- Do not remove, skip, or weaken unrelated tests.
- Do not broaden scope beyond the contract.
