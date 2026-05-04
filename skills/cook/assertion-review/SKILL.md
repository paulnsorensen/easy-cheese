---
name: assertion-review
description: Optionally map spec requirements to strong assertions.
license: MIT
---

# /cook/assertion-review

Source: adapted from `paulnsorensen/cheese-flow.git` for the Easy Cheese hierarchical skill layout.

## Goal

Optionally map spec requirements to strong assertions.

## Inputs

An approved spec, pasted requirements, or focused request plus outputs from prior cook sub-skills.

## Instructions

1. Use when press flagged uncertain coverage or multi-requirement drift risk.
2. Map each spec requirement to assertions.
3. Recommend ready, cut rerun, implement correction, or spec amendment.

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
