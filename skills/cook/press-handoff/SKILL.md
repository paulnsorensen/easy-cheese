---
name: press-handoff
description: Hand green changes to `/press` for coverage hardening.
license: MIT
---

# /cook/press-handoff

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Hand green changes to `/press` for coverage hardening.

## Inputs

An approved spec, pasted requirements, or focused request plus outputs from prior cook sub-skills.

## Instructions

1. Confirm narrow tests are green.
2. Pass spec summary, changed files, and test results to `/press`.
3. Stop if implementation is partial or skipped.

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
