---
name: mold
description: Shape a fuzzy idea into a grounded spec through mode, evidence, seam, approval, and artifact sub-skills.
license: MIT
---

# /mold

Source: adapted from `paulnsorensen/cheese-flow.git` while keeping this repository skills-only and portable.

## Use when

The user has a fuzzy feature idea, bug symptom, or design direction and wants a coherent spec or issue set before implementation.

## Do not use when

The user wants free-form discussion with no artifact intent, direct implementation, or research-only output.

## Sub-skills

| Sub-skill | Purpose |
| --- | --- |
| `/mold/mode-route` | Pick the starting mode from the user input. |
| `/mold/dialogue` | Build shared understanding through focused questions. |
| `/mold/ground` | Verify load-bearing claims with evidence. |
| `/mold/options` | Compare viable options and non-goals. |
| `/mold/seams` | Sketch public seams before writing a spec. |
| `/mold/approval` | Run the approval gate for artifact type, slug, and path. |
| `/mold/artifacts` | Write only the approved spec or issue drafts. |

Default order: `/mold/mode-route` → `/mold/dialogue` → `/mold/ground` → `/mold/options` → `/mold/seams` → `/mold/approval` → `/mold/artifacts`

Run only the sub-skills needed for the user request, but do not skip a gate that protects correctness or user intent.

## Output

Produce an approved `.cheese/specs/<slug>.md` spec and optional `.cheese/issues/<slug>-NNN.md` issue drafts, or explain what remains blocked.

## Rules

- Dialogue first; artifacts are the by-product.
- Do not implement code.
- Do not write files before approval.
