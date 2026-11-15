# Review fan-out policy: default /simplify and /code-review versus /age

Comparison of how three review surfaces decide **how many agents to run, what
each one receives, and what happens to the findings**: the built-in `/simplify`
and `/code-review` skills in Claude Code v2.1.261, and easy-cheese's `/age`.
The default prompts were read out of the CLI binary (`strings -n 8` over
`~/.local/share/mise/installs/aqua-anthropics-claude-code/v2.1.261/claude`,
string-table lines ~380,000-380,700) and confirmed by loading `/simplify`
through the Skill tool. `/age` facts come from `skills/age/` at `6dd17839`
plus PR #667. Per-angle prompt text and the dimension-by-dimension comparison
live in the sibling page
[review-dimensions-prompt-comparison](./review-dimensions-prompt-comparison.md).

## TL;DR

- `/simplify` is a fixed four-agent fan-out. Four default `Agent` workers, one cleanup angle each, dispatched in one message, then the parent applies fixes in place. No severity, no verifier, no read-only enforcement.
- `/code-review` is an effort ladder keyed by the parent model. The default level is medium: 8 finder agents, up to 6 candidates each, one verifier agent per deduped candidate, cap 8 findings. xhigh and max run 10 finders, a verifier per candidate, and one sweep finder, cap 15. Low runs no agents at all.
- `/age` is router-sized. A weighted review-surface score picks 1, 2, or 5 lenses; risk overrides promote dimensions into solo lenses, up to 9. Workers are the pinned read-only `reviewer` agent at the router's effort, fed an 8-component packet, computing severity themselves. The parent reconciles, a cheap verifier runs only at n>1, and fixes are deferred to `/cure`.
- The measured gap: both default prompts say "all in a single message so they run concurrently". `skills/age/references/fan-out.md` never says that, and [fanout-patterns-2026-09-10](../analytics/fanout-patterns-2026-09-10.md) found zero same-second bursts across 609 spawns and no `/age` run with three or more reviewers. `/age`'s n=5 exists on paper only.

## Default /simplify

| Axis | Value |
| --- | --- |
| Trigger | `/simplify [<target>]`. Diff from `git diff @{upstream}...HEAD` plus `git diff HEAD` for working-tree changes |
| Width | Fixed 4. Single-pass inline fallback when the Agent tool is absent, with a mandatory "this was single-pass" disclaimer in the summary |
| Worker | `Agent` tool with no `subagent_type`, so the default general-purpose agent: parent model inherited, full tool set, not read-only |
| Worker input | The diff and one ~50-word angle: Reuse, Simplification, Efficiency, Altitude |
| Finding shape | `file`, `line`, one-line `summary`, "the concrete cost (what is duplicated, wasted, or harder to maintain)" |
| Severity | None |
| Reconcile | Parent dedups "findings that point at the same line or mechanism" |
| Verify | None |
| Apply | Parent fixes each remaining finding directly. Skip when the fix "would change intended behavior, require changes well outside the reviewed diff, or that you judge to be a false positive". Skips are noted, not argued |
| Output | Chat summary of fixed and skipped |

## Default /code-review

Effort resolves to the last level the user typed, else medium. Each level maps
to a prompt cell, and the cell table is keyed by the parent model (`re` in the
binary): `default`, `claude-sonnet-5`, `claude-opus-4-8`, `claude-opus-5`. A
model outside the table, including Fable, uses `default`.

| Level | `default` cell | `claude-sonnet-5` | `claude-opus-4-8` | `claude-opus-5` |
| --- | --- | --- | --- | --- |
| low | 1 diff pass, no agents, skips test files, cap 4 | Same, but targets `min(files_changed, 4)` | Same as default | Same as default |
| medium | 8 finders x 6 candidates, 1 verifier per candidate, cap 8. "Precision" lead-in | Same | 8 angles inline, dedup, no verify, cap 8 | Minimal single-pass prompt, no agents, cap 15 |
| high | 8 finders x 6, recall-biased verify, cap 10 | Same plus a finder-budget hint | 8 angles inline, no verify, cap 10 | Same minimal prompt |
| xhigh / max | 10 finders x 8, 1 verifier per candidate, 1 sweep finder, cap 15 | Same plus budget hint | 10 angles inline plus an inline sweep | Falls back to the opus-4.8 xhigh cell |

The eight angles at medium and high are A line-by-line diff scan, B
removed-behavior auditor, C cross-file tracer, Reuse, Simplification,
Efficiency, Altitude, and Conventions (CLAUDE.md). xhigh adds D language-pitfall
specialist and E wrapper/proxy correctness. The finder-budget hint is
`ceil(diff_lines / 150)` clamped to 2..8 and tells the parent to scale the
finder count to the diff instead of running a fixed fleet.

Finders are told: "Pass every candidate with a nameable failure scenario
through — finders that silently drop half-believed candidates bypass the verify
step and are the dominant cause of misses."

Verification is one `Agent` call per deduped candidate, given the diff, the
relevant files, and the candidate. It returns exactly one of CONFIRMED,
PLAUSIBLE, or REFUTED. Medium keeps CONFIRMED and PLAUSIBLE. High and above add
"PLAUSIBLE by default" and allow REFUTED only when constructible from the code.
Output goes through the `ReportFindings` tool when the host exposes it,
otherwise a JSON array. `--fix` applies in place; `--comment` posts inline PR
comments.

## /age today

Router internals are on [age-fanout-router](../architecture/age-fanout-router.md).
The policy as the skill prompts state it:

| Axis | Value |
| --- | --- |
| Width | `route(score, risk_flags)`: score under 60 gives 1, 60..250 gives 2, over 250 gives 5. A hit on an `OVERRIDE_FLAGS` token promotes its dimension into a solo lens, so n can reach 6 or 9. Never fan out when `/age` is itself a sub-agent |
| Effort | `high` on any override or score over 900, `low` at n=1, else `medium`. Passed to every worker |
| Worker | `reviewer` from `~/.claude/agents/reviewer.md`: opus, `maxTurns: 50`, Edit/Write/NotebookEdit/Agent/Grep/Glob denied, must receive a `Review mode: severity-report` line or return `blocked: missing-contract` |
| Worker input | `.cheese/age/<slug>-packet.md` with eight components: located spec, dependency manifests, project-helper index, path-context map, the lens's rubric slice plus location and fix-cost sections, the severity formula, the output contract with `also-relevant-to`, and the dedup-ownership statement. Plus the review-context digest (`skills/age/references/packet.md`) |
| Finding shape | Dimension tag, `path:line`, claim, location tier, fix-cost-now, fix-cost-later, confidence, recommendation, optional invariants (PR #667) |
| Severity | Computed by the worker: base tier from the dimension table, plus one for `location = contract` on location-sensitive dimensions, plus one for `fix-cost-later = structural`, capped at blocker (`skills/age/references/dimensions.md:21-40`) |
| Reconcile | Seam 4: the parent applies the 15-rule dimension-boundary table only to lines two workers flagged or one worker tagged `also-relevant-to` |
| Verify | Seam 6, n>1 only: `verifier` role at cheap power and low effort, batches of up to ten, one verdict per claim: confirm, downgrade-or-drop, or escalate to `## Confidence`. No verifier at n=1 |
| Apply | Never. `review-lock` rejects the report if the production tree moved. `/cure` applies the selected ids with the recommendation as the locked decision |
| Output | `.cheese/age/<slug>.md` behind a handoff preamble, parsed by `src/easy_cheese/shared/findings.py` |

On PR #667's diff the router scored 338 and returned n=5 at medium effort with
the base lens partition.

## Side by side

| Axis | `/simplify` | `/code-review` (medium, `default` cell) | `/age` |
| --- | --- | --- | --- |
| Width policy | Fixed 4 | Fixed 8 finders, then N verifiers | Score-driven 1/2/5, promoted up to 9 |
| Parallel dispatch | Explicit: "all in a single message" | Explicit, same wording | Not stated; measured as serial |
| Worker definition | Default general-purpose | Default general-purpose | Pinned read-only `reviewer`, opus |
| Context per worker | Diff plus one paragraph | Diff plus one paragraph | 8-component packet plus digest |
| Per-worker evidence | Grep on demand | Grep on demand | Shared caller graph and helper index, computed once |
| Severity | None | None; "most-severe first" by judgement | Formula, worker-computed |
| Verification | None | 1 agent per candidate at every level from medium up | Batched cheap verifier, only at n>1 |
| Cross-dimension reconciliation | Dedup by line or mechanism | Dedup by defect, location, reason | 15-rule boundary table |
| Gap sweep | None | xhigh and max only | None |
| Write policy | Parent edits immediately | `--fix` edits immediately | Locked; fixes via `/cure` |
| Effort keyed by model | No | Yes, four model cells | No, router only |
| Diff-size scaling | No | sonnet-5 cells only | Yes, via score |

## Observed versus designed

[fanout-patterns-2026-09-10](../analytics/fanout-patterns-2026-09-10.md)
measured 83 sessions: no parallel bursts anywhere, 51 `/age` runs with zero
reviewers and 73 with one or two, and 72 of 148 reviewer prompts missing the
`Review mode` line with zero `blocked` returns. The default skills avoid the
first two failures by construction: the width is a literal number in the prompt
and the dispatch instruction names the single-message form. `/age`'s width is
correct on paper and has not been exercised.

## Implications

1. `fan-out.md` Seam 3 needs the literal dispatch instruction the default has: one message, `len(lenses)` Agent calls, background where the harness allows it.
2. `/age` verifies nothing at n=1. The default verifies every candidate from medium up. A cheap per-claim verifier at n=1 is the cheapest recall win available.
3. The default has no equivalent of the packet, the severity formula, the boundary table, the review lock, or the cure seam. Those are the moat. The fan-out mechanics are the gap.

_Source: binary string extraction and Skill load of Claude Code v2.1.261; `skills/age/` at `6dd17839`; PR #667 · Updated: 2026-09-12_
