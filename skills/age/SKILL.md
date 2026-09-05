---
name: age
description: >-
  Review a diff, PR, branch, or path across ten dimensions. Emit a severity-grouped findings report.
  Use when the user wants a code review. Trigger on "review this", "/age", "is this safe to merge", or "find bugs".
  Also trigger on "spot security issues", "check for slop", "review my PR", or "what's wrong with this code".
  Review every requested dimension. Review all ten dimensions by default.
  Do not apply fixes. Route them to /cure.
  Do not harden tests; route that work to /press.
license: MIT
metadata: {dispatches-agents: true}
---

# /age

Review a diff or scoped path before merging or after `/press`. Use this skill whenever the user wants evidence-backed observations rather than an approval verdict. Do not apply fixes in this skill. Let `/cure` apply them.

## Inputs

```text
/age [<ref-or-range>] [--scope <path>]... [--slug <slug>] [--full] [--safe] [--open-pr] [--auto] [--hard] [--html]
/age <slug> [--full] [--safe] [--open-pr] [--auto] [--hard] [--html]
```

Repeat `--scope <path>` for each reviewed path.
Every report needs a slug.
Take the slug from the `<slug>` form.
Take it from `--slug <slug>` on a scoped or range review.
Derive it with `slugify` only when the caller supplies neither.
A caller in a pipeline always passes the pipeline slug.

`--full` expands the `## Low` section when ten or more low-severity findings exist.
The default report collapses that section to a one-line summary.

`--safe` re-introduces cure selection.
`--open-pr` propagates through `/cure` to terminal `/plate`.
A new PR follows `/plate`'s explicit-choice and review-shape policy.

For a `<slug>`, resolve `.cheese/press/<slug>.md` (if present) for press context.
Review the current working diff.
For a `<ref-or-range>`, review that range.
Review the current working diff when the user supplies neither input.
If the base branch is unclear, ask or use the repository's documented default.

`--auto` is the propagated autonomous-mode flag from `/cook --auto`.
See `## Handoff` and `references/handoff-detail.md` § Auto mode for the cap rule and the full chain.

`handoff_context.wiki_hits` is optional routed input from `/cheese`.
Each hit carries `page`, `line`, and `why`.
Reuse each valid hit before you ground the review again.
Render the reused hits in `## Wiki context`.

`--hard` propagates through `/cure` to `/plate`.
Age never fires the gate.
`/plate` gives `/hard-cheese` the final verified artifact state before publication.

`--html` emits a static HTML copy alongside `.cheese/age/<slug>.md`.
Write the markdown first.
Then run `python3 skills/age/scripts/age.pyz html-report --report .cheese/age/<slug>.md --slug <slug>`.
Print the returned path.
The HTML groups findings by severity into the shared HTML shell.
The output is offline and uses no CDN or JS.

Read [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md) for helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions.
Prefer the bundled or repo-local helper.
Treat `${CLAUDE_SKILL_DIR}` as an optional host-provided fallback.
The handoff blocks below define the portable contract.
Remember: slash commands are host renderings, not the control model.

## Review dimensions

Dimensions answer **what kind of problem**.
Assign one severity (`blocker / high / medium / low`) to each finding.
Compute severity from base, location, and compounding modifiers (see `references/dimensions.md` § Severity computation).

| Dimension | Base range |
| --- | --- |
| correctness | low → blocker |
| security | low → blocker |
| encapsulation | low → blocker |
| spec | low → blocker |
| complexity | low → high |
| deslop | low → high |
| assertions | low → blocker |
| nih | low → high |
| efficiency | low → blocker |
| telemetry | low → blocker |

`references/dimensions.md` contains per-dimension base-severity tables, location sensitivity, fix-cost-now / fix-cost-later, and recommendation shapes.
Read it before computing any finding's severity.
This workflow intentionally omits the git-history/precedent dimension.

## Flow

1. Identify the diff, scope, and relevant specification or issue.
   Compute the review range's `review_surface` score and risk flags.
   Call `age_route.route(score=..., risk_flags=..., entry="age")` from `src/easy_cheese/shared/fanout/age_route.py`.
   For `n=1`, continue with steps 2 through 4.
   For `n>1`, read `references/fan-out.md` first.
   Use its `lenses` list to set the worker count.
   Do not use fan-out when `/age` runs as a sub-agent.
   Pass the router's `effort` value to the reviewer.
   Assemble the fan-out packet before the lock.
   The lock covers the packet, because the packet is review evidence.
   Then run `python3 skills/age/scripts/age.pyz review-lock --slug <slug>` to lock the production tree.
   Use the resolved slug from `## Inputs`.
   Step 5 rejects the report when a production file changes.
2. Gather evidence from the diff, touched files, tests, and callers/imports.
   Resolve the upstream report with `python3 skills/age/scripts/age.pyz artifact-path --phase press --slug <slug>`.
   Validate its preamble with `python3 skills/age/scripts/age.pyz read-handoff-slug --phase press --slug <slug>`.
   That command returns preamble fields only.
   Read the resolved file itself for the `## Review follow-ups` section and every unresolved item.
   Copy each unresolved item into a `## Press findings` sub-section.
   Keep the `artifact` and `baseline` values from that preamble for step 5.
   `/cure` reads only `.cheese/age/<slug>.md`.

If no press report exists but a cook handoff exists, record `press: skipped` (see `## Output`).
Print the warning at handoff.
If no cook artifact exists either, omit the marker and continue.
If `.cheese/glossary/<slug>.md` exists, read it to flag naming drift as a deslop finding.
3. Review every dimension.
   Omit dimensions with no findings.
   Report every defect, however minor.
   Do not filter findings by perceived significance.
   The verifier pass (`n>1`) or severity computation (single-parent) filters findings later.
   Do not report a gate failure that matches the diff's recorded `baseline:` block.
   Read [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md) for the baseline rules.
   Report only new or changed failures.
4. Compute severity per finding (base + location bump + compounding bump, capped at `blocker`).
   Group findings by severity (`## Blocker → ## High → ## Medium → ## Low`).
   Order findings by file within each severity group.
5. Write the report body to `.cheese/age/<slug>-body.md`.
   Write the body only. Do not write the handoff preamble into that file.
   Do not write `.cheese/age/<slug>.md` yourself. The gated writer creates it.
   Compute the recommended set first (see `## Handoff`).
   Set `<next>` to `cure` when that set is not empty.
   Set `<next>` to `done` when that set is empty.
   Set `<artifact>` to the upstream report path from step 2. Use `""` only when no upstream report exists.
   Set `<baseline>` to the baseline block from that upstream handoff. Omit `--baseline` only when the upstream handoff has none.
   Run `python3 skills/age/scripts/age.pyz write-handoff-artifact --phase age --slug <slug> --status ok --next <next> --artifact "<artifact>" --orientation "<one-line orientation>" --durable-flags "<none | one line per flag>" --baseline "<baseline>" --body-file ".cheese/age/<slug>-body.md"`.
   Print the path.
   The write fails when the production tree moved after step 1. Do not retry it with a new lock.
6. Hand off (see `## Handoff` below).

## Sub-agent fan-out

`/age` sizes its own fan-out with the age router (`src/easy_cheese/shared/fanout/age_route.py`), not a size-only threshold.
`/age` resolves every dispatched worker through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).
Use read-only, fresh-context workers.
See `references/fan-out.md`, `references/packet.md`, and `references/sub-agent-gate.md` for mechanics.

Call each source-code backend through the shared [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md) contract.
`references/packet.md` § Evidence tools and fallbacks lists the tool for each need.

## Output

Use [`../cheese/references/formatting.md`](../cheese/references/formatting.md) for cross-cutting house style and citation form.
This section defines the findings-report shape.
`formatting.md` defines the voice rules and footnote primitive.

The gated writer writes `.cheese/age/<slug>.md`.
It puts the minimum handoff slug at the top.
The slug carries `status`, `next`, `artifact`, `durable_flags`, `baseline`, and one-line orientation.
Supply each value through the step 5 command.
Write the body below into `.cheese/age/<slug>-body.md`, with no preamble.
`references/report-example.md` § Body order defines the section order, the exact
finding format, and the full skeleton. Read it before you write the body.

Use the voice-kernel scale for per-finding `confidence:` (see `references/voice.md` § Reasoning posture).
Use `certain` for direct evidence from a diff/code read or command output.
Use `speculating` for an inference from an indirect signal.
Do not ship a `don't know` grading as a finding row.
Gather the missing evidence or drop the claim.
Reserve `don't know` for the report-level `## Confidence` line.
Add suppressed lows to the cure-selection table only when the user passes `--full`.

Set `status: ok` when the review completes.
Set `status: halt: <reason>` when the review cannot reach evidence.
Follow the [handback contract](../cheese/references/handback-contract.md).
Derive `next` from the recommended set that `## Handoff` computes.
Set `next: cure` when that set is not empty.
Set `next: done` when that set is empty.
Keep every finding in the report, whatever `next` says.
Set `durable_flags:` to `none` by default, as in cook's gate.
When the review-surface score exceeds 400, set `durable_flags: coverage-degraded: review-surface score <score> exceeds the 400-point ceiling` and lead `## Next step` with a stacked-split recommendation for `/plate`.
Record the resolved worker types under `## Agent resolution` in the body.

Print `Age report: .cheese/age/<slug>.md`.
When `press: skipped` is set, print the following warning:
`Warning: no /press report for <slug> — hardening was skipped. Run /press <slug> first, or continue with /cure.`
When the user passes `--html`, print the HTML path that `html-report` returns.
The render command appears under `--html` in `## Inputs`.

## Handoff

**Pipeline:** culture → mold → cook → press → **[age]** → cure → plate

**Compute the recommended set.** Use the `all-medium, cheap` composite.
Include the medium floor (blocker+high+medium).
Also include every `Low` with `fix-cost-now: contained`.

**Decide whether to act or ask.**

This selection is the only one. `## Output` derives `next` from it.
A review with contained lows and no medium finding has a non-empty set.
That review sets `next: cure` and keeps every low finding in the report.

- **Empty set** — Set `next: done`. Print the report path. Stop.
- **Reason to ask** — Ask when a set member has `fix-cost-now: sprawling` or `fix-cost-later: structural`.
  Also ask when two findings conflict.
  Also ask when the user passes `--safe`.
  Read `references/handoff-detail.md` first.
  Render the gate per [`../cheese/references/handoff-gate.md`](../cheese/references/handoff-gate.md).
  Pre-select the composite. Mark each heavy row.
- **Otherwise** — Act. Announce the selection. Dispatch `/cure` per `references/handoff-detail.md` § Dispatch. Do not render a gate.

`--auto` substitutes a severity-floor selection and its own chain.
Read `references/handoff-detail.md` § Auto mode before an `--auto` run.
That file also defines the no-chain override under `/cook`'s fan pathway.

## Rules

Review is not a verdict.
Explain where to look and why.
Do not edit production files.
The step 1 review lock enforces this rule.
`/cure` applies each fix.
Do not raise a finding for a gate failure identical to the diff's recorded `baseline:` block.
Flag only new/changed failures per [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md).
Default to acting.
Auto-select the recommended set.
Dispatch `/cure` without a gate.
Ask first only for a genuine reason or when `--safe` is active.
Treat an empty recommended set as a clean stop, not a question.
Do not invent evidence.
Cite files, diffs, commands, or unavailable-source notes.
Agree when the diff is fine.
Treat an empty dimension as a valid outcome, not a gap to fill.
Keep confidence qualitative (`certain | speculating | don't know`) in the report and each finding.
Never use a numeric score.
Give each finding a location and recommendation.
Do not add JSON sidecars or tag-anchored fix payloads.
`/cure` reads the markdown directly.
Apply `references/voice.md` (output discipline, reasoning posture, confidence vocabulary).

## References

- Read the generated command inventory in [`references/commands.md`](references/commands.md).
- Read `references/dimensions.md` before grading a finding.
- Read `references/fan-out.md` before an `n>1` dispatch.
- Read `references/packet.md` before assembling a fan-out context packet.
- Read `references/sub-agent-gate.md` before a sub-agent dispatch.
- Read `references/handoff-detail.md` before the selection gate or a `/cure` dispatch.
- Read `references/report-example.md` § Body order before writing the report body.
- Read `references/packet.md` § Evidence tools and fallbacks before gathering evidence.
- Read `references/handoff-detail.md` § Auto mode before an `--auto` run.
- Read `references/voice.md` before writing the report.
- Read the applicable [Rust](references/deslop-rust.md), [TypeScript](references/deslop-typescript.md), [Python](references/deslop-python.md), [Shell](references/deslop-shell.md), or [Go](references/deslop-go.md) catalog before grading `deslop`.

## Agent resolution

Resolve every dimension worker and fresh-context review through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Review a diff or one dimension | reviewer | read-only, fresh-context | powerful | high | compatible reviewer, then general |

The table gives the default effort.
The router overrides it. Use the `low`, `medium`, or `high` value that `age_route.route(...)` returns.
Pass that value to every dispatched worker.

The report body carries the shared `agent_resolution` block under `## Agent resolution`.
`references/report-example.md` shows that section in the full skeleton.
