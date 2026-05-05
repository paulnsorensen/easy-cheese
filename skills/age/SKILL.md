---
name: age
description: This skill should be used when the user wants a code review on a diff, PR, branch, or path — phrases like "review this", "/age", "is this safe to merge", "find bugs", "spot security issues", "check for slop", "review my PR", "look for problems", "what's wrong with this code". Runs eight orthogonal review dimensions (correctness, security, encapsulation, spec, complexity, deslop, assertions, NIH) over the scoped diff and emits a stake-grouped findings report. Use even when the user only asks for one dimension — the report scopes itself. Findings only — no fixes; route the user to `/cure` once they pick what to act on.
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
| correctness | high | broken behaviour, silent failures, ordering, null/empty edge cases |
| security | high | auth, injection, secrets, unsafe parsing, tainted inputs |
| encapsulation | high | boundary leaks, cross-slice internals, public API sprawl |
| spec | high | drift from stated requirements or acceptance criteria |
| complexity | medium | unnecessary nesting, long functions, speculative abstractions |
| deslop | medium | dead code, AI residue, duplicated logic, vague names |
| assertions | medium | weak tests, shallow existence checks, swallowed errors |
| nih | medium | reinvented dependency, stdlib, or existing project helper |

Per-dimension rubrics and recommendation shapes in `references/dimensions.md`. Easy Cheese intentionally drops the `precedent` (git-history) dimension; that lives in cheese-flow proper.

## Flow

1. Identify the diff, scope, and relevant spec or issue.
2. Gather evidence: diff, touched files, tests, callers/imports.
3. Review every dimension; dimensions with no findings simply omit themselves.
4. Group findings by stake (high → medium) and by file.
5. Write the report to `.cheese/age/<slug>.md` and print the path.
6. Recommend `/cure <slug>` only after the user picks findings to act on. Never auto-invoke `/cure`.

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
Next step:  /cure <slug>
```

## Rules

- Review is not a verdict; explain where to look and why.
- Do not edit production files.
- Do not invent evidence. Cite files, diffs, commands, or unavailable-source notes.
- Keep confidence qualitative (`low | medium | high`); never emit a numeric score.
- Findings carry location + recommendation. Do not write JSON sidecars or hash-anchored fix payloads — `/cure` reads the markdown directly.
