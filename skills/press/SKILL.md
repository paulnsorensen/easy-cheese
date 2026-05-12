---
name: press
description: This skill should be used right after `/cook` produces green changes, when the user wants the test surface hardened before review or shipping — phrases like "press the changes", "harden this", "check coverage", "strengthen the tests", "are the tests good enough", "press before /age", "/press". Reads the spec + cooked diff, maps changed behavior to tests, finds weak assertions and missing boundaries, adds focused hardening tests, writes a press report to `.cheese/press/<slug>.md`, and prompts `/age` next. Supports `--auto` (propagated from `/cook --auto`) to skip its handoff and chain straight into `/age --auto` when readiness is `ready for /age`. Use even when the user wants to "tighten things up" before review. Do NOT use to add broad new behavior — only corrective fixes that hardening tests force. After `/cook`; before `/age` → `/cure`.
license: MIT
---

# /press

Use this skill after `/cook` has produced green implementation changes and before review or shipping.

Do not use it to implement broad new behavior. Press may add or strengthen tests and make tiny corrective fixes only when a test exposes a clear defect in the cooked scope.

## Flow

1. **Read** — load the spec or acceptance criteria and the cooked diff.
2. **Map** — for each changed behaviour, find the test(s) that cover it via `cheez-search`.
3. **Gap analysis** — identify weak assertions, missing boundaries, and uncovered integration seams. See `references/gap-analysis.md` for what counts as a gap and the priority order.
4. **Add focused tests** — observe red first when behaviour changes. Use `cheez-write` for precise edits.
5. **Corrective fixes** — only for defects the hardening tests expose. No new behaviour.
6. **Run checks** — narrowest useful tests, then relevant wider gates already in the project.
7. **Report** — write `.cheese/press/<slug>.md` (slug carried from `/cook`, or derived from branch/task) and print the path. Mark readiness: `ready for /age`, `follow-up recommended`, or `blocked`.
8. **Hand off** — prompt the next step via `AskUserQuestion` (see `## Handoff` below). Never auto-invoke.

## Preferred tools and fallbacks

Code search, reading, and editing all go through the cheez-* skills (`/cheez-search`, `/cheez-read`, `/cheez-write`) — see those skills for tool selection rules. For coverage and test discovery, press uses `cheez-search` (callers via `kind: "callers"`) and `tilth_deps` (cheez-search owns the routing).

Beyond cheez-* there are press-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diff review | `delta` | plain `git diff` |
| Affected execution flows + risk scoring | code-review-graph: `get_affected_flows_tool`, `get_impact_radius_tool` | manual flow tracing from callers |

**Freshness:** before the first code-review-graph query in a run, call `build_or_update_graph_tool` (and `embed_graph_tool` if you'll use `semantic_search_nodes_tool` to find shared-concept tests under divergent names). See [`/cheez-search`](../cheez-search/SKILL.md#when-code-review-graph-beats-tilth-if-your-harness-has-it) for the full freshness contract and when semantic search beats tilth.

If optional tools are missing, press a narrower surface and state the residual risk.

## Testing priority

1. Spec compliance: promised behavior has executable coverage.
2. Assertion strength: tests fail for wrong values, errors, or state.
3. Boundary behavior: empty, missing, malformed, minimal, and maximum inputs.
4. Integration seams: filesystem, subprocess, network, time, or dependency failure when in scope.
5. Happy path regression: the primary user path still passes.

## Output

Write to `.cheese/press/<slug>.md` and print the path. The report shape:

```markdown
# Press Report — <slug>

## Orientation
<one or two factual sentences about what /cook changed>

## Checks run
- <command>: <pass|fail|skipped with reason>

## Findings
| Severity | Category | Evidence | Recommendation |
| --- | --- | --- | --- |

## Coverage
- Spec coverage:
- Boundary coverage:
- Assertion strength:

## Readiness
<ready for /age | follow-up recommended | blocked>

## Next step
<ready for /age>:           /age <slug>           — review the cooked + pressed diff
<follow-up recommended>:    address open findings, then /age <slug>
<blocked>:                  resolve blocking issues before proceeding
```

Then print:

```
Press report: .cheese/press/<slug>.md
Next step:    /age <slug>                       (when ready for /age)
              address open findings, then /age  (when follow-up recommended)
              blocked — resolve before continuing (when blocked)
```

## Handoff

After the press report is on disk, ask via `AskUserQuestion` which downstream to run. Default options:

- **Run /age `<slug>`** *(recommended when readiness is `ready for /age`)* — review the diff.
- **Stop** — address `follow-up recommended` items before review.

Pre-select `Run /age` only when readiness is `ready for /age`. If the report is `blocked`, do not pre-select anything; the user decides whether to fix or escalate.

### Auto mode

When invoked with `--auto` (propagated from `/cook --auto`):

- Skip the `AskUserQuestion` entirely.
- If readiness is `ready for /age`, invoke `/age <slug> --auto` directly.
- If readiness is `follow-up recommended` or `blocked`, stop the auto chain and surface the press report to the user. Do not paper over a non-green press in auto mode — those statuses exist precisely because human judgement is needed.

## Rules

- Do not weaken assertions.
- Do not broaden implementation beyond the cooked contract.
- Surface medium and high findings explicitly; summarize low findings.
- If the cooked diff or spec rests on a false premise (the contract is wrong, or the test surface is solving the wrong problem), stop and surface the premise before adding tests; do not harden the wrong angle.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead the press report with the readiness verdict, flag residual risk as `certain | speculating | don't know`, agree when coverage is already sufficient without manufacturing tests.
