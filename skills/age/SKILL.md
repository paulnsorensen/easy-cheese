---
name: age
description: This skill should be used when the user wants a code review on a diff, PR, branch, or path — phrases like "review this", "/age", "is this safe to merge", "find bugs", "spot security issues", "check for slop", "review my PR", "look for problems", "what's wrong with this code". Runs eight orthogonal review dimensions (correctness, security, encapsulation, spec, complexity, deslop, assertions, NIH) over the scoped diff and emits a stake-grouped findings report at `.cheese/age/<slug>.md`. Use even when the user only asks for one dimension — the report scopes itself. Findings only — no fixes; after the report lands, age renders the cure-selection table inline and asks which findings to cure (no "should I run /cure?" meta-question), then hands off to `/cure` with the selection locked in. After `/press` (optional); before `/cure`.
license: MIT
---

# /age

Use this skill to review a diff or scoped path before merging, after `/press`, or whenever the user wants evidence-backed observations rather than an approval verdict.

Do not use it to apply fixes directly. Hand fix work to `/cure`, which owns applying findings.

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
6. Hand off via `AskUserQuestion` (see `## Handoff` below). Age owns the selection gate: it asks the user *which findings to cure*, never *whether to run /cure*. `/cure` still owns the actual fix application — age never auto-applies fixes.

## Preferred tools and fallbacks

Code search and reading go through the cheez-* skills (`/cheez-search`, `/cheez-read`) — see those skills for tool selection rules. For caller graphs specifically, age uses `cheez-search` with `kind: "callers"` and `tilth_deps` (cheez-search owns the routing).

Beyond cheez-* there are review-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diff inspection | `delta` | `git diff --unified=3` |
| Risk-scored impact + curated review context | code-review-graph: `get_review_context_tool`, `get_impact_radius_tool`, `detect_changes_tool` | `tilth_deps` + manual scoping |
| Architecture / hotspot framing for large diffs | code-review-graph: `get_architecture_overview_tool`, `get_hub_nodes_tool`, `get_bridge_nodes_tool` | skip and note in confidence |
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
<`certain` | `speculating` | `don't know`> — <one-line justification including which evidence sources were unavailable>

## Next step
Selection prompt rendered inline — pick findings to cure or `none` to stop.
```

Then print:

```
Age report: .cheese/age/<slug>.md
```

## Handoff

After the report is on disk, skip any "should I run /cure?" meta-question and go straight to the selection gate. The user's working memory is on the findings, not on whether a follow-up step exists.

1. Render the numbered selection table per `../cure/references/selection.md` directly inline (one row per finding, grouped by stake).
2. Ask via `AskUserQuestion` which findings to cure. Offer the recognized selection verbs as options:
   - **Pick findings** — accept a free-text reply using the verbs from `../cure/references/selection.md` (`1,3,5`, `all-high`, `all`, `none`, `skip N`).
   - **All high-stake** *(recommended when at least one high-stake finding exists)* — equivalent to `all-high`.
   - **Stop** — equivalent to `none`; leave the report for later.
3. On a non-empty selection, hand off to `/cure <slug>` with the selection locked in (pass the chosen ids through so `/cure` skips its own selection prompt and goes straight to apply). `/cure` still owns the apply / validate / report loop and may surface the chosen ids for confirmation if the report has shifted underneath it.
4. On `none` / `Stop`, exit cleanly with the report path.

Never auto-apply fixes, and never invoke `/cure` without an explicit non-empty selection. The default selection remains empty.

## Rules

- Review is not a verdict; explain where to look and why.
- Do not edit production files.
- Do not auto-apply fixes. Age owns the *selection* gate (which findings to cure) and dispatches `/cure` only with an explicit non-empty selection; the *application* gate stays inside `/cure`.
- Do not invent evidence. Cite files, diffs, commands, or unavailable-source notes.
- Agree when the diff is fine. Do not manufacture findings to fill a dimension; an empty dimension is a valid outcome.
- Keep confidence qualitative (`certain | speculating | don't know`); never emit a numeric score.
- Findings carry location + recommendation. Do not write JSON sidecars or hash-anchored fix payloads — `/cure` reads the markdown directly.
- Apply `references/voice.md` (output discipline, reasoning posture, confidence vocabulary).

## References

- `references/dimensions.md` — per-dimension rubrics and recommendation shapes.
- `references/voice.md` — shared output discipline, reasoning posture, and confidence vocabulary.
