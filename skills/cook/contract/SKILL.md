---
name: contract
description: Confirm behavior, non-goals, scope, and quality gates.
license: MIT
---

# /cook/contract

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Confirm behavior, non-goals, scope, and quality gates.

## Inputs

An approved spec, pasted requirements, or focused request plus outputs from prior cook sub-skills.

## Instructions

1. Summarize behavior to build, explicit non-goals, likely scope, and quality gates.
2. Ask for missing acceptance criteria if needed.
3. Proceed only when the contract is clear enough for a failing test.

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
