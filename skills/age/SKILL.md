---
name: age
description: This skill should be used when the user wants a code review on a diff, PR, branch, or path — phrases like "review this", "/age", "is this safe to merge", "find bugs", "spot security issues", "check for slop", "review my PR", "look for problems", "what's wrong with this code". Runs eight orthogonal review dimensions (correctness, security, encapsulation, spec, complexity, deslop, assertions, NIH) over the scoped diff and emits a stake-grouped findings report at `.cheese/age/<slug>.md`. Use even when the user only asks for one dimension — the report scopes itself. Findings only — no fixes; route the user to `/cure` when they are ready to select findings. After `/press` (optional); before `/cure`.
license: MIT
---

# /age

Use this skill to review a diff or scoped path before merging, after `/press`, or whenever the user wants evidence-backed observations rather than an approval verdict.

Do not use it to apply fixes directly. Hand fix work to `/cure`, which owns selecting and applying findings.

## Inputs

Accept:

```text
/age [<ref-or-range>] [--scope <path>] [--comprehensive]
/age <slug>
```

When called with a `<slug>`, resolve `.cheese/press/<slug>.md` (if present) for press context and review the current working diff. When called with a `<ref-or-range>`, review that range. Default to the current working diff when neither is supplied. If the base branch is unclear, ask or use the repository's documented default.

## Review dimensions

| Dimension | Stake | Look for |
| --- | --- | --- |
| correctness | high | broken behaviour, silent failures, ordering, null/empty edge cases |
| security | high | auth, injection, secrets, unsafe parsing, tainted inputs |
| encapsulation | high | boundary leaks, cross-slice internals, public API sprawl |
| spec | high | drift from stated requirements or acceptance criteria |
| complexity | medium | unnecessary nesting, long functions, speculative abstractions |
| deslop | medium | dead code, AI residue, duplicated logic, vague names |
| assertions | medium | weak tests, shallow existence checks, swallowed errors |
| nih | medium | reinvented dependency, stdlib, or existing project helper |

Per-dimension rubrics and recommendation shapes in `references/dimensions.md`. This reduced workflow intentionally omits the git-history/precedent dimension.

## Flow

1. Identify the diff, scope, and relevant spec or issue.
2. Gather evidence: diff, touched files, tests, callers/imports. If `.cheese/press/<slug>.md` exists, read it and include a `## Press findings` sub-section in the age report summarising unresolved items — `/cure` reads only `.cheese/age/<slug>.md` and cannot access the press report directly.
3. Review every dimension; dimensions with no findings simply omit themselves.
4. Group findings by stake (high → medium) and by file.
5. Write the report to `.cheese/age/<slug>.md` and print the path.
6. Hand off via `AskUserQuestion` (see `## Handoff` below). `/cure` owns the finding-selection gate; age never auto-applies fixes.

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

Write to `.cheese/age/<slug>.md`:

```markdown
# Age Report — <slug>

## Orientation
<one or two factual sentences about what the diff does>

## High-stake findings
- **[correctness]** `path/to/file.ts:42-50` — <what is wrong, in plain terms>. <recommendation>.
- **[security]** `path/to/handler.ts:108` — <what is wrong>. <recommendation>.

## Medium-stake findings
- **[complexity]** `path/to/util.ts:200-240` — <what is wrong>. <recommendation>.
- **[deslop]** `path/to/old.ts:55-60` — <what is wrong>. <recommendation>.

## Confidence
<low|medium|high> — <one-line justification including which evidence sources were unavailable>

## Next step
/cure <slug>   — pick findings to fix
```

Then print:

```
Age report: .cheese/age/<slug>.md
```

## Handoff

After the report is on disk, ask via `AskUserQuestion` which downstream to run. Default options:

- **Run /cure `<slug>`** *(recommended when there are high-stake findings)* — pick findings to fix.
- **Stop** — leave the report for later.

Pre-select `Run /cure` when at least one high-stake finding exists. `/cure` still owns its selection gate; the user picks individual findings there. Never auto-apply.

## Rules

- Review is not a verdict; explain where to look and why.
- Do not edit production files.
- Do not auto-apply fixes. Prompting `/cure` via `AskUserQuestion` is fine; bypassing `/cure`'s selection gate is not.
- Do not invent evidence. Cite files, diffs, commands, or unavailable-source notes.
- Keep confidence qualitative (`low | medium | high`); never emit a numeric score.
- Findings carry location + recommendation. Do not write JSON sidecars or hash-anchored fix payloads — `/cure` reads the markdown directly.
