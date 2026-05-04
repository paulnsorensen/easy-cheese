---
name: age
description: Lightweight staff-engineer review that inspects a diff across correctness, security, complexity, encapsulation, spec fit, precedent, deslop, assertions, and NIH risk.
license: MIT
---

# /age

Use this skill to review a diff or scoped path before merging, after `/press`, or whenever the user wants evidence-backed observations rather than an approval verdict.

Do not use it to apply fixes directly. Hand fix work to `/cure` after the user chooses what to address.

## Inputs

Accept:

```text
/age [<ref-or-range>] [--scope <path>] [--comprehensive]
```

Default to the current working diff when no ref is supplied. If the base branch is unclear, ask or use the repository's documented default.

## Review dimensions

| Dimension | Stake | Look for |
| --- | --- | --- |
| correctness | high | broken behavior, silent failures, ordering, null/empty edge cases |
| security | high | auth, injection, secrets, unsafe parsing, tainted inputs |
| encapsulation | high | boundary leaks, cross-slice internals, public API sprawl |
| spec | high | drift from stated requirements or acceptance criteria |
| complexity | medium | unnecessary nesting, long functions, speculative abstractions |
| deslop | medium | dead code, AI residue, duplicated logic, vague names |
| assertions | medium | weak tests, shallow existence checks, swallowed errors |
| nih | medium | reinvented dependency, stdlib, or existing project helper |
| precedent | advisory | conflict with local patterns or nearby history |

## Flow

1. Identify the diff, scope, and relevant spec or issue.
2. Gather evidence: diff, touched files, tests, callers/imports, and precedent.
3. Review all dimensions, letting non-applicable dimensions no-op.
4. Group observations by stake and location.
5. Produce a concise report and optional fix/suggestion handoff list.
6. Recommend `/cure` only after the user chooses to act on findings.

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diff inspection | `delta` | `git diff --unified=3` |
| Structural search | `sg`, Serena or LSP | `ripgrep`, `find`, targeted reads |
| Dependency/caller graph | code review graph, tilth deps | import searches, caller searches, test references |
| GitHub/PR context | `gh` | local git commands or user-provided PR data |
| Merge/conflict awareness | mergiraf | manual conflict checks |

Missing optional tools should not block review. State which evidence was unavailable and reduce confidence accordingly.

## Output

```markdown
## Age Report

### Orientation
<what changed, factually>

### High-stake findings
- <dimension>: <evidence> → <recommendation>

### Medium-stake findings
- <dimension>: <evidence> → <recommendation>

### Advisory notes
- <dimension>: <evidence> → <recommendation>

### Handoff
- Fix candidates for `/cure`:
- Suggestions for human judgment:
- Confidence: <low|medium|high>
```

## Rules

- Review is not a verdict; explain where to look and why.
- Do not edit production files.
- Do not invent evidence. Cite files, diffs, commands, or unavailable-source notes.
- Keep confidence qualitative.
