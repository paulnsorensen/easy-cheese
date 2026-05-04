---
name: culture
description: No-write thinking space for architecture, trade-offs, and ambiguous problems decomposed into dialogue sub-skills.
license: MIT
---

# /culture

Source: adapted from `paulnsorensen/cheese-flow.git` while keeping this repository skills-only and portable.

## Use when

The desired output is shared understanding, not files, commits, specs, or PRs.

## Do not use when

The user wants a written spec, implementation, review, or external evidence gathering.

## Sub-skills

| Sub-skill | Purpose |
| --- | --- |
| `/culture/restate` | Restate the question or tension. |
| `/culture/constraints` | Identify assumptions, constraints, and decision criteria. |
| `/culture/tradeoffs` | Explore options and likely blast radius. |
| `/culture/light-evidence` | Use light evidence without turning into deep research. |
| `/culture/summary` | End with shared understanding and next step. |

Default order: `/culture/restate` → `/culture/constraints` → `/culture/tradeoffs` → `/culture/light-evidence` → `/culture/summary`

Run only the sub-skills needed for the user request, but do not skip a gate that protects correctness or user intent.

## Output

Return a short conversational summary with current understanding, trade-offs, open questions, and a suggested next step.

## Rules

- No writes, no commits, no PRs.
- If concrete work is needed, stop and recommend the next skill.
