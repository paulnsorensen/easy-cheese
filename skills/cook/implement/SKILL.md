---
name: implement
description: Make the cut tests pass with minimal edits.
license: MIT
---

# /cook/implement

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Make the cut tests pass with minimal edits.

## Inputs

An approved spec, pasted requirements, or focused request plus outputs from prior cook sub-skills.

## Instructions

1. Read the failing tests and affected production code.
2. Make the smallest production change that passes the cut tests.
3. Preserve strong assertions and avoid speculative behavior.

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
