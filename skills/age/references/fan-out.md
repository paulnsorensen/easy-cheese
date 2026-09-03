# Router call and lens fan-out mechanics

Read this before any `n>1` dispatch from `SKILL.md § Flow` step 1 / `§ Sub-agent fan-out`.

## Router call

Compute the review range's `review_surface` score with `python3 skills/age/scripts/age.pyz review-surface --repo . <base>...HEAD`.
The range must be the diff under review.
Use `<base>...HEAD` for an already-committed branch.
Use the bare working diff otherwise.
Never rely on the CLI's bare default.
It scores the working tree against `HEAD` and silently zeroes an already-committed branch.
Grep added lines outside `skills/**` and `.hallouminate/**` for the bundled age router's risk flags to populate `risk_flags`.
Scope this search so a diff that only documents the override vocabulary does not trip its own tokens.
A missed token means no promoted lens, not a missing security lens.
Treat each hit as a hint, not a guarantee.
Then call:

```python
from src.fanout.age_route import route
route(score=<float>, risk_flags=[...], entry="age")
```

If the host only ships the bundle, `echo '{"score": <float>, "risk_flags": [...], "entry": "age"}' | python3 skills/age/scripts/age.pyz age-route` is the fallback (JSON on stdin, route JSON on stdout).

## Lens fan-out mode (n>1)

The router activates this mode when `n>1` and `/age` is not itself a sub-agent.
Dispatch one worker per **lens** in the router's returned `lenses` list, not per dimension.
Dispatch exactly `len(lenses)` workers.
The router returns `n` in `{1, 2, 5}`.
The base ladder uses these score bands before any override promotion:

- A score `<60` returns `n=1`.
- A score from `60–250` returns `n=2`.
- A score `>250` returns `n=5`.
- A score `>900` selects high effort.

The base ladder partitions lenses at `n>1`, before any override promotion:

- `n=2` — `[correctness, spec, assertions, security, telemetry]` / `[encapsulation, complexity, deslop, nih, efficiency]`.
- `n=5` — the five cohesion-grouped lenses: `[correctness, spec, assertions]`; `[security, telemetry]`; `[encapsulation, complexity]`; `[deslop, nih]`; `[efficiency]`.

An override promotion (mechanics above) pulls its mapped dimension from the group that the base tier selected.
It gives that dimension a solo lens.
The group's remaining members stay together in one lens.
Each grouping above serves thematic cohesion.
At `n=5`, `encapsulation` never shares a lens with `efficiency` or `telemetry`.

The seam sequence below stays identical for every `n>1`.
Only worker count and each worker's assigned dimension set vary with `n`.

**Seam 1 — Predicate.** Use the predicate defined at the section opener above.

**Seam 2 — Shared context packet.** The orchestrator assembles the packet once and writes it to `.cheese/age/<slug>-packet.md`.
Each worker reads that packet.
`packet.md` documents its eight components and the review-context digester that supplies the orientation block.

**Seam 3 — Worker contract.** Use one worker per lens.
Resolve the `reviewer` role through `../../cheese/references/agent-resolution.md` at the router's `effort` dial.
Require read-only permissions and fresh context.
Allow a prompt-constrained general fallback only with `degraded: true`.
Each worker:
- Reviews every dimension in its assigned lens. A solo-lens worker reviews one dimension. A multi-dimension lens worker reviews every dimension in its group. For example, the `[correctness, spec, assertions]` worker reviews all three.
- Computes **full per-finding severity** for every dimension in its lens (base + location bump + compounding bump).
- Tags each finding with its dimension and an `also-relevant-to: [<dim>, ...]` field when it suspects cross-dimension overlap. Include overlap with a dimension owned by a *different* lens.
- Reports every defect it notices, however minor. It does not perform severity-conservative self-filtering. The verifier pass (Seam 6) and orchestrator reconciliation (Seam 4) filter findings.
- Returns full per-finding rows in the `SKILL.md § Output` finding format (`**[dim:sev]** path:line — claim` + `location / fix-cost-now / fix-cost-later / confidence` + `recommendation`). This is not an orientation digest. The `§ Digest contract` size ceiling does not apply.
- Does **not** dedup, apply boundary tiebreakers, reconcile severity across dimensions or lenses, or write the report.

After all workers return, continue at Seam 4 (reconciliation) below.

**Seam 4 — Orchestrator reconciliation.** After all workers return, apply the `## Dimension boundaries` table (`dimensions.md` § Dimension boundaries) verbatim.
Apply it to a line that meets either condition:
1. Two or more workers flag the same `file:line`.
2. Any worker tags the line `also-relevant-to: [d]`.
Re-evaluate dimension `d` against that line.
Apply the tiebreaker.
Keep the higher-base finding, suppress it, or emit both with a cross-reference, as the 15 rules require.
This consumes the `also-relevant-to` signal.
It provides the cross-dimension coverage that single-parent gets for free.
Do not reconcile a line unless two or more workers flag it or a worker tags it `also-relevant-to`.
Group findings by severity.
The parent owns the canonical artifact.
After reconciliation, continue at Seam 6 (verifier pass).
Then continue at step 5 (write + print the report path) and `SKILL.md § Handoff` exactly as the single-parent path does.

**Seam 5 — Shared impact evidence.** The packet carries the caller/dependency notes assembled through `tilth_deps` and the selected semantic caller search.
Workers use that packet instead of rebuilding impact context independently.

**Seam 6 — Verifier pass.** After Seam 4 reconciliation produces the candidate findings list, use a cheap `verifier` role.
Use the haiku/tiny tier and `effort: low` from the Roles x tiers table.
Check each reconciled finding against the evidence slice cited in its `recommendation`/location fields.
Make one verifier call per finding.
Constrain the schema to "verify exactly one claim".
Three outcomes:
- **Confirm** — The cited evidence supports the claimed severity. Ship the finding unchanged.
- **Downgrade/drop** — The evidence does not support the claimed severity or the claim itself. The verifier lowers the severity tier or drops the finding. The orchestrator records the original claim and the verifier's reasoning in the report's confidence trail.
- **Escalate** — The evidence given cannot settle the claim either way. Cross-cutting contract 1 states: "a claim no evidence can settle returns `escalate`, never a guessed pass or fail". Keep the finding at its **original** severity and add an `escalate` flag. Never silently drop it or pass it through without a flag.

The verifier runs the "cheap severity-filter leg" from the Roles x tiers table whenever `n>1`.
It does not run at `n=1`.
The single-parent path has no reconciliation step to filter.
The reviewer's own severity computation is the only grading pass.

**Output shape invariant.** The findings report (`.cheese/age/<slug>.md`) uses the same dedup, severity grouping, and finding format in the single-parent path and every lens fan-out width.
Resolution provenance may expose the selected role and topology.
