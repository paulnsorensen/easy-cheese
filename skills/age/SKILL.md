---
name: age
description: This skill should be used when the user wants a code review on a diff, PR, branch, or path — phrases like "review this", "/age", "is this safe to merge", "find bugs", "spot security issues", "check for slop", "review my PR", "look for problems", "what's wrong with this code". Runs nine orthogonal review dimensions (correctness, security, encapsulation, spec, complexity, deslop, assertions, NIH, efficiency) over the scoped diff and emits a stake-grouped findings report at `.cheese/age/<slug>.md`. Use even when the user only asks for one dimension — the report scopes itself. Findings only — no fixes; after the report lands, age renders the cure-selection table inline and asks which findings to cure (no "should I run /cure?" meta-question), then hands off to `/cure` with the selection locked in. Supports `--auto` (propagated from `/cook --auto`) for the autonomous chain into `/cure` (see `### Auto mode`). After `/press` (optional); before `/cure`.
license: MIT
---

# /age

Use this skill to review a diff or scoped path before merging, after `/press`, or whenever the user wants evidence-backed observations rather than an approval verdict.

Do not use it to apply fixes directly. Hand fix work to `/cure`, which owns applying findings.

## Inputs

Accept:

```text
/age [<ref-or-range>] [--scope <path>] [--comprehensive] [--auto]
/age <slug> [--auto]
```

When called with a `<slug>`, resolve `.cheese/press/<slug>.md` (if present) for press context and review the current working diff. When called with a `<ref-or-range>`, review that range. Default to the current working diff when neither is supplied. If the base branch is unclear, ask or use the repository's documented default.

`--auto` is the propagated autonomous-mode flag from `/cook --auto`. It changes the handoff (see `## Handoff`). Track the cure-pass count internally so the two-cure-pass cap can be enforced — increment after each `/cure --auto` returns. The full chain is `age → cure → age → cure → age → stop`: up to three `/age --auto` invocations and up to two `/cure --auto` passes. Once two cure passes have completed, the next `/age --auto` writes the final report and stops without invoking `/cure` again. (This in-session contract uses conversation memory to track passes — it works because `/cook --auto` runs every phase in the same context. When invoked from `/ultracook`, each phase boots in fresh context with no shared memory; see `### When invoked from /ultracook` below for the no-shared-memory variant.)

`--hard` is the propagated metacognitive-gate flag from `/cook --hard` (or `/cheese --hard`). Age does not fire the gate; it only passes `--hard` forward to `/cure` at the handoff so the gate can fire at the share-for-review boundary. See `skills/hard-cheese/SKILL.md`.

## Review dimensions

| Dimension | Stake | Look for |
| --- | --- | --- |
| correctness | high | broken behaviour, silent failures, ordering, null/empty edge cases |
| security | high | auth, injection, secrets, unsafe parsing, tainted inputs |
| encapsulation | high | boundary leaks, cross-slice internals, public API sprawl |
| spec | high | drift from stated requirements or acceptance criteria |
| complexity | medium | unnecessary nesting, long functions, speculative abstractions, redundant state, parameter sprawl, stringly-typed code |
| deslop | medium | dead code, AI residue, duplicated logic, copy-paste-with-variation, vague names |
| assertions | medium | weak tests, shallow existence checks, swallowed errors |
| nih | medium | reinvented dependency, stdlib, or existing project helper / utility / component |
| efficiency | medium | unnecessary work, missed concurrency, hot-path bloat, no-op updates, time-of-check/time-of-use (TOCTOU) pre-checks, memory leaks, overly broad reads |

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

**Freshness:** before the first code-review-graph query in a run, call `build_or_update_graph_tool` (and `embed_graph_tool` if you'll use `semantic_search_nodes_tool`). The graph is persistent and goes stale between sessions. See [`/cheez-search`](../cheez-search/SKILL.md#when-code-review-graph-beats-tilth-if-your-harness-has-it) for the full freshness contract and when semantic search beats tilth — steel threads across renamed layers, concepts under divergent names, spec-vs-code vocabulary mismatch.

Missing optional tools should not block review. State which evidence was unavailable and reduce confidence accordingly.

## Sub-agent context gate

`/age` should fork a read-only review-context sub-agent when evidence gathering is likely to exceed the parent context, especially for `--comprehensive` reviews.

Spawn when any of these are true:

- The diff spans more than 15 files.
- Touched code or generated review context is larger than roughly 25 KB (about 5 K tokens of raw output the parent would not read line-by-line).
- Caller / dependency graph expansion crosses multiple subsystems.
- code-review-graph or `tilth_deps` output is needed for hotspot, bridge-node, or blast-radius framing.

The sub-agent returns a digest: orientation paragraph, high-signal `path:line` citations, gap list. The parent owns the nine-dimension review, severity grading, and the `.cheese/age/<slug>.md` report. Do not spawn for small diffs, to outsource severity grading, or to outsource the final verdict.

Digest size, parent-vs-sub-agent split, and harness-agnostic sub-agent selection live in `references/sub-agent-gate.md` — single source of truth for the cross-cutting rules.

## Output

Write to `.cheese/age/<slug>.md` with a minimum handoff slug at the top so `/ultracook` and `/cheese --continue` can chain without re-parsing the report:

```markdown
status: ok | halt: <one-line reason>
next: cure | done
artifact: <path-to-press-report-or-prior-cure-if-any>
<one-line orientation: what the diff does>

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

`status: ok` when the review completed. `status: halt: <reason>` when evidence was unreachable in a way that blocks honest review. `next: cure` when at least one medium-or-above finding exists and the chain has cure passes remaining; `next: done` when no medium-or-above findings remain or the two-cure-pass cap has been reached.

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

Outside `--auto`, never auto-apply fixes and never invoke `/cure` without an explicit non-empty selection. The default selection remains empty. `--auto` substitutes a stake-floor selection — see `### Auto mode` below.

### Auto mode

When invoked with `--auto`:

- Skip the `AskUserQuestion`.
- If two cure passes have already completed (cap reached), stop and surface the final report — do not invoke `/cure` again even if findings remain.
- Otherwise, if any medium-or-above finding exists, invoke `/cure <slug> --auto --stake medium+` and increment the cure-pass count when it returns.
- If no medium-or-above findings remain, stop the chain with a one-line "auto chain clean" note and the report path.

### When invoked from /ultracook

`/ultracook` spawns age as a fresh-context sub-agent and owns the chain itself. Honour the no-chain override:

- Write `.cheese/age/<slug>.md` (with the handoff slug at the top) and stop. Do not invoke `/cure <slug> --auto --stake medium+` from inside the sub-agent.
- Set `next:` from what you observe on this run, not from any guess about chain position. `next: cure` when at least one medium-or-above finding exists; `next: done` when none do.
- The two-cure-pass cap is enforced by ultracook's fixed chain length, not by age's `next:` field. Fresh-context age cannot count prior cure passes anyway, so this is the only honest contract. The orchestrator uses `next: done` for early-stop signalling; the natural terminal stop is the chain table running out of entries.

### Inline-degrade mode (invoked from a sub-agent, e.g. /cheese-factory atom worker)

When `/age` detects it is running as a sub-agent (the parent passes the `invoked-from: cheese-factory-atom` marker or equivalent context line in the prompt), it runs its nine dimensions inline within its own context instead of spawning per-dimension sub-agents. This honours the host's nesting-depth limit (Claude Code allows 1 level of sub-agent nesting; equivalents in other harnesses are similar).

Detection mechanism: scan the invoking prompt for an `invoked-from:` line — values like `cheese-factory-atom`, `fromagerie-atom`, or any harness-specific marker the orchestrator passes in. When present, switch modes:

- Run every dimension's review inline. Do not fork the read-only review-context sub-agent gate (`## Sub-agent context gate` above is skipped under inline-degrade).
- Output (the findings report + handoff slug) is identical between fan-out and inline-degrade modes — only the internal execution differs.
- Honour the no-chain-forward directive as usual: write the slug and stop. Do not invoke `/cure` from the sub-agent — the orchestrator owns the chain.

Inline-degrade is forced when the marker is present; there is no opt-out. Spawning a level-2 sub-agent from inside an atom worker would silently exceed the harness's nesting limit and fail — the marker is the only honest signal that the parent has already consumed level-1 depth.

## Rules

- Review is not a verdict; explain where to look and why.
- Do not edit production files.
- Do not auto-apply fixes. Age owns the *selection* gate (which findings to cure) and dispatches `/cure` only with an explicit non-empty selection; the *application* gate stays inside `/cure`. The only sanctioned bypass of either gate is `--auto`, which `/cure` enforces with a stake floor and `/age` enforces with a two-pass cap.
- Do not invent evidence. Cite files, diffs, commands, or unavailable-source notes.
- Agree when the diff is fine. Do not manufacture findings to fill a dimension; an empty dimension is a valid outcome.
- Keep confidence qualitative (`certain | speculating | don't know`); never emit a numeric score.
- Findings carry location + recommendation. Do not write JSON sidecars or hash-anchored fix payloads — `/cure` reads the markdown directly.
- Apply `references/voice.md` (output discipline, reasoning posture, confidence vocabulary).

## References

- `references/dimensions.md` — per-dimension rubrics and recommendation shapes.
- `references/voice.md` — shared output discipline, reasoning posture, and confidence vocabulary.
- `references/sub-agent-gate.md` — shared sub-agent kernel: digest contract, harness-agnostic selection, what the parent never delegates.
