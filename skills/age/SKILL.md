---
name: age
description: Lightweight staff-engineer review across correctness, security, encapsulation, spec, complexity, deslop, assertions, and NIH sub-skills.
license: MIT
---

# /age

Source: adapted from `paulnsorensen/cheese-flow.git` while keeping this repository skills-only and portable.

## Use when

The user wants an evidence-backed diff or path review before merging, after `/press`, or before selecting fixes.

## Do not use when

The user wants fixes applied directly; hand that to `/cure` after selecting findings.

## Sub-skills

| Sub-skill | Purpose |
| --- | --- |
| `/age/orient` | Identify diff, scope, and relevant spec or issue. |
| `/age/correctness` | Review broken behavior, silent failures, ordering, null/empty edge cases. |
| `/age/security` | Review auth, injection, secrets, unsafe parsing, and tainted inputs. |
| `/age/encapsulation` | Review boundary leaks, cross-slice internals, and public API sprawl. |
| `/age/spec` | Review drift from stated requirements or acceptance criteria. |
| `/age/complexity` | Review unnecessary nesting, long functions, speculative abstractions. |
| `/age/deslop` | Review dead code, AI residue, duplicated logic, and vague names. |
| `/age/assertions` | Review weak tests, shallow existence checks, and swallowed errors. |
| `/age/nih` | Review reinvented dependency, stdlib, or existing project helper. |
| `/age/synthesize` | Group observations by stake and produce the report. |

Default order: `/age/orient` → `/age/correctness` → `/age/security` → `/age/encapsulation` → `/age/spec` → `/age/complexity` → `/age/deslop` → `/age/assertions` → `/age/nih` → `/age/synthesize`

Run only the sub-skills needed for the user request, but do not skip a gate that protects correctness or user intent.

## Output

Return an Age Report with orientation, high-stake findings, medium-stake findings, advisory notes, handoff, and qualitative confidence.

## Rules

- Review is not a verdict; cite where to look and why.
- Do not edit production files.
- Do not invent evidence.
