---
name: press
description: This skill should be used right after `/cook` produces green changes, when the user wants the test surface hardened before review or shipping — phrases like "press the changes", "harden this", "check coverage", "strengthen the tests", "are the tests good enough", "press before /age", "/press". Reads the spec + cooked diff, maps changed behavior to tests, finds weak assertions and missing boundaries, adds focused hardening tests, writes a press report to `.cheese/press/<slug>.md`, and prompts `/age` next. Supports `--auto` (propagated from `/cook --auto`) to skip its handoff and chain straight into `/age --auto` when readiness is `ready for /age` or `follow-up recommended`; only `blocked` halts the auto chain. Use even when the user wants to "tighten things up" before review. Do NOT use to add broad new behavior — only corrective fixes that hardening tests force. After `/cook`; before `/age` → `/cure`.
license: MIT
---

# /press

Use this skill after `/cook` has produced green implementation changes and before review or shipping.

Do not use it to implement broad new behavior. Press may add or strengthen tests and make tiny corrective fixes only when a test exposes a clear defect in the cooked scope.

## --hard propagation

`/press --hard` (propagated from `/cook --hard`) is pass-through only. Press runs no gate. Hand `--hard` forward to `/age` at the handoff so it eventually reaches `/cure`, which is the only pipeline skill that fires the metacognitive vibecheck. See `skills/hard-cheese/SKILL.md`.

## Flow

1. **Read** — load the spec or acceptance criteria and the cooked diff.
2. **Map** — for each changed behaviour, find the test(s) that cover it via `cheez-search`.
3. **Gap analysis** — identify weak assertions, missing boundaries, and uncovered integration seams. See `references/gap-analysis.md` for what counts as a gap and the priority order.
4. **Add focused tests** — observe red first when behaviour changes. Use `cheez-write` for precise edits.
5. **Corrective fixes** — only for defects the hardening tests expose. No new behaviour.
6. **Run checks** — narrowest useful tests, then relevant wider gates already in the project.
7. **Report** — write `.cheese/press/<slug>.md` (slug carried from `/cook`, or derived from branch/task) and print the path. Mark readiness: `ready for /age`, `follow-up recommended`, or `blocked`.
8. **Hand off** — in manual mode, prompt the next step via the shared handoff gate (see `## Handoff` below); in `--auto` mode, chain forward per `### Auto mode`.

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

Cross-cutting house style and citation form: [`../../shared/formatting.md`](../../shared/formatting.md). This section owns the press-report shape; formatting.md owns the voice rules and the footnote primitive.

Write to `.cheese/press/<slug>.md` with a minimum handoff slug at the top so `/ultracook` and `/cheese --continue` can chain without re-parsing the report. Compose the report body in a tmp file, then write the artifact atomically with the canonical 4-line preamble (`status: <ok|halt: …>` / `next: <age|done>` / `artifact: <path>` / `<orientation>`) via `${CLAUDE_SKILL_DIR}/scripts/common.pyz write_handoff_artifact`. Pass `--phase press` so the file lands in press's own directory; `--artifact` carries the *prior* phase's report (cook), not press's own:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/common.pyz write_handoff_artifact \
    --slug <slug> \
    --status "ok" \
    --phase "press" \
    --next "age" \
    --artifact ".cheese/cook/<slug>.md" \
    --orientation "<one-line: what press did — e.g., added 4 boundary tests; no defects exposed>" \
    --body-file <tmp-body>
```

For `blocked`, pass `--status "halt: <reason>"` and `--next "done"`. The script renders the preamble and writes `.cheese/<phase>/<slug>.md` atomically (tmp + rename) so readers never see a half-written file. The body content follows the preamble after a blank line. Body shape:

```markdown
# Press Report — <slug>

## Orientation
<one or two factual sentences about what press did this pass — the hardening added, the gaps closed, the readiness verdict. `/cheese --continue` surfaces the slug's orientation line to the user as "where you are", so press's orientation must describe press's own work, not duplicate cook's orientation.>

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
<follow-up recommended>:    /age <slug>           — review-safe; documented follow-ups addressed after review
<blocked>:                  resolve blocking issues before proceeding
```

`status: ok` maps to readiness `ready for /age` or `follow-up recommended` (both are review-safe — the cooked contract is sound and every changed behaviour has a hardening test). `status: halt: <reason>` maps to readiness `blocked` with the reason filled in. `next: age` when readiness is `ready for /age` or `follow-up recommended`; `next: done` only when readiness is `blocked` so the orchestrator stops the chain.

Then print:

```
Press report: .cheese/press/<slug>.md
Next step:    /age <slug>                          (when ready for /age or follow-up recommended)
              blocked — resolve before continuing  (when blocked)
```

## Handoff

**Pipeline:** culture → mold → cook → **[press]** → age → cure → ship

After the press report is on disk, ask via the shared handoff gate in [`../../shared/handoff-gate.md`](../../shared/handoff-gate.md). Lead each option with the verb (what the user wants to *do* next); the skill command (with any in-scope `--hard` propagation) is the backing detail. Default options:

- **Review the diff** *(recommended when readiness is `ready for /age` or `follow-up recommended`)* — `/age <slug>`. For `follow-up recommended`, the cooked contract is sound and every changed behaviour has a hardening test; documented follow-ups can be addressed after review.
- **Stop** — dispatch none; defer review (use this if you want to harden manually before /age, even though the contract is review-safe).

Pre-select **Review the diff** when readiness is `ready for /age` or `follow-up recommended`. If the report is `blocked`, do not pre-select anything; the user decides whether to fix or escalate. After a non-stop selection, run the selected command immediately.

### Auto mode

When invoked with `--auto` (propagated from `/cook --auto`):

- Skip the handoff gate entirely.
- If readiness is `ready for /age` or `follow-up recommended`, invoke `/age <slug> --auto` directly. Both states mean the cooked contract is sound and every changed behaviour has a hardening test; follow-ups are documented and review-safe.
- If readiness is `blocked`, stop the auto chain and surface the press report to the user. `blocked` is reserved for cases where human judgement is genuinely required: a false premise on the cooked contract, an unfixable level-1/2 gap inside cooked scope, a changed behaviour press could not lock with a stable hardening test, or spinning wheels (three attempts at the same gap without green).

### When invoked from /ultracook

`/ultracook` spawns press as a fresh-context sub-agent and owns the chain itself. When the spawn prompt explicitly says "for THIS PHASE ONLY" and "do not chain forward to the next phase," honour the override: write `.cheese/press/<slug>.md` (with the handoff slug at the top) and stop. Do not invoke `/age <slug> --auto` from inside the sub-agent regardless of readiness. The orchestrator reads the handoff slug and either chains to age (when `next: age`) or halts (when `next: done`).

## Rules

- Do not weaken assertions.
- Do not broaden implementation beyond the cooked contract.
- **Every changed behaviour in the cooked diff leaves press with an executable hardening test that would fail if the change regressed.** Even on a 3-line off-by-one fix, press writes (or confirms cook wrote) a test like `test_off_by_one_at_boundary` that locks the fix in. If press cannot produce a stable hardening test for a changed behaviour (flaky seam, missing infrastructure, design decision required), readiness is `blocked` — never `ready for /age` or `follow-up recommended`.
- **Cap iteration at three attempts per gap.** Count test-edit + run cycles. On the third failed cycle on the same gap, mark readiness `blocked` with reason `spinning: <gap-description>` and surface the report. Do not loop indefinitely.
- Surface medium and high findings explicitly; summarize low findings.
- If the cooked diff or spec rests on a false premise (the contract is wrong, or the test surface is solving the wrong problem), stop and surface the premise before adding tests; do not harden the wrong angle.
- Apply the shared voice kernel (lives at `skills/age/references/voice.md` in this repo): lead the press report with the readiness verdict, flag residual risk as `certain | speculating | don't know`, agree when coverage is already sufficient without manufacturing tests.
