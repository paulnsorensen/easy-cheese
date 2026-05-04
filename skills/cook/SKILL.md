---
name: cook
description: Implement a clear spec with cheese-flow-inspired contract, cut, implement, taste-test, press, assertion-review, and package sub-skills.
license: MIT
---

# /cook

Source: adapted from `paulnsorensen/cheese-flow.git` while keeping this repository skills-only and portable.

## Use when

The user has an approved spec, pasted requirements, or a precise implementation request with acceptance criteria.

## Do not use when

The request is fuzzy planning, no-write discussion, or review-only work.

## Sub-skills

| Sub-skill | Purpose |
| --- | --- |
| `/cook/contract` | Confirm behavior, non-goals, scope, and quality gates. |
| `/cook/cut` | Create failing tests before production changes. |
| `/cook/implement` | Make the cut tests pass with minimal edits. |
| `/cook/taste-test` | Check spec drift, readability, and scope before hardening. |
| `/cook/press-handoff` | Hand green changes to `/press` for coverage hardening. |
| `/cook/assertion-review` | Optionally map spec requirements to strong assertions. |
| `/cook/package-report` | Produce the package-ready checklist and handoff. |

Default order: `/cook/contract` → `/cook/cut` → `/cook/implement` → `/cook/taste-test` → `/cook/press-handoff` → `/cook/assertion-review` → `/cook/package-report`

Run only the sub-skills needed for the user request, but do not skip a gate that protects correctness or user intent.

## Output

Summarize files changed, checks run, risks, and whether the work is ready for `/press`, `/age`, or `/cure`.

## Rules

- Keep changes scoped to the accepted contract.
- Use existing dependencies and project commands.
- Stop when implementation reveals unanswered design decisions.
