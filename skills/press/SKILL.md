---
name: press
description: Harden cooked changes through contract, test map, gap analysis, focused tests, fixes, checks, and report sub-skills.
license: MIT
---

# /press

Source: adapted from `paulnsorensen/cheese-flow.git` while keeping this repository skills-only and portable.

## Use when

`/cook` has produced green implementation changes and the user wants coverage and assertion hardening before review or shipping.

## Do not use when

The user wants broad new behavior or speculative implementation.

## Sub-skills

| Sub-skill | Purpose |
| --- | --- |
| `/press/read-contract` | Read the spec, acceptance criteria, and cooked diff. |
| `/press/map-tests` | Map changed behavior to existing and new tests. |
| `/press/gap-analysis` | Find weak assertions, boundaries, and integration gaps. |
| `/press/add-tests` | Add focused hardening tests for meaningful gaps. |
| `/press/corrective-fixes` | Apply only tiny fixes exposed by hardening tests. |
| `/press/run-checks` | Run relevant existing checks. |
| `/press/report` | Report readiness, follow-up, or blocked. |

Default order: `/press/read-contract` → `/press/map-tests` → `/press/gap-analysis` → `/press/add-tests` → `/press/corrective-fixes` → `/press/run-checks` → `/press/report`

Run only the sub-skills needed for the user request, but do not skip a gate that protects correctness or user intent.

## Output

Return a Press Report with checks, findings, coverage notes, and handoff status.

## Rules

- Do not weaken assertions.
- Do not broaden implementation beyond the cooked contract.
- Surface medium and high findings explicitly.
