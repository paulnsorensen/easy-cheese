---
name: cure
description: Fix selected review findings through load, selection, apply, validate, re-age, and shipping report sub-skills.
license: MIT
---

# /cure

Source: adapted from `paulnsorensen/cheese-flow.git` while keeping this repository skills-only and portable.

## Use when

`/age`, failed validation, or selected review findings need focused fixes and shipping preparation.

## Do not use when

The user has not selected findings and has not approved a default; do not apply everything automatically.

## Sub-skills

| Sub-skill | Purpose |
| --- | --- |
| `/cure/load` | Load selected findings or review reports. |
| `/cure/select` | Gate on explicit user selection. |
| `/cure/apply` | Apply approved fixes by the right handler. |
| `/cure/validate` | Run relevant existing validation. |
| `/cure/re-age` | Re-review touched paths with age principles. |
| `/cure/ship-report` | Prepare PR-ready status and residual risks. |

Default order: `/cure/load` → `/cure/select` → `/cure/apply` → `/cure/validate` → `/cure/re-age` → `/cure/ship-report`

Run only the sub-skills needed for the user request, but do not skip a gate that protects correctness or user intent.

## Output

Return a Cure Report with applied items, deferred items, checks, re-review notes, and next step.

## Rules

- Nothing applies without explicit selection or approval.
- Keep fixes scoped to selected findings.
- Do not hide failed or skipped checks.
