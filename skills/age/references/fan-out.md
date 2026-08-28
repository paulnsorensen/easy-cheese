# Router call and lens fan-out mechanics

Read this before any `n>1` dispatch from `SKILL.md § Flow` step 1 / `§ Sub-agent fan-out`.

## Router call

Compute the review range's `review_surface` score through `python3 skills/age/scripts/age.pyz review-surface --repo . <base>...HEAD`. The range must be the diff under review (`<base>...HEAD` for an already-committed branch, the bare working diff otherwise); never rely on the CLI's bare default, which scores the working tree against `HEAD` and silently zeroes an already-committed branch. Grep the diff's **added lines outside `skills/**` and `.hallouminate/**`** for the bundled age router's risk flags to populate `risk_flags` — scoped so a diff that merely documents the override vocabulary does not trip its own tokens; a missed token means no promoted lens, not a missing security lens, so treat a hit as a hint, not a guarantee. Then call:

```python
from src.fanout.age_route import route
route(score=<float>, risk_flags=[...], entry="age")
```

If the host only ships the bundle, `echo '{"score": <float>, "risk_flags": [...], "entry": "age"}' | python3 skills/age/scripts/age.pyz age-route` is the fallback (JSON on stdin, route JSON on stdout).

The returned `n` is the fan-out mode. The base ladder is `n ∈ {1, 2, 5}` from `score` alone (`<60` → 1, `60–250` → 2, `>250` → 5), with `n=1` reviewed single-parent (no fan-out) via `SKILL.md § Flow` steps 2–4, unchanged; `effort` (`low`/`medium`/`high`) dials the reviewer dispatch; `overrides_hit` names any risk-override token matched (auth/secrets/crypto, tenant isolation, payments/ledgers, concurrency/idempotency/ordering/retries, schema/migration/protocol/public-API change, production-destructive ops, weak integration coverage — see `age_route.OVERRIDE_FLAGS` for the exact grep tokens). An override no longer forces the top tier: it **promotes** its mapped dimension out of whichever base-ladder group the score placed it in, into its own solo lens — the group's remaining members stay grouped as one lens. `n` climbs by however many dimensions were promoted, uncapped, with a natural maximum of 9 when all four override categories hit simultaneously at the top score tier. `effort` is `high` whenever any override hits **or** `score` exceeds 900; `low` only at `n=1` (unreachable with an override, since an override always forces `high`); `medium` otherwise.

Independently of the router's `n`, `/age` may still fork a read-only review-context sub-agent — preferably the `explorer` phase-agent — purely for evidence-gathering (not fan-out) when caller/dependency graph expansion from `tilth_deps` or the selected semantic caller search crosses multiple subsystems, especially for `--comprehensive` reviews. This is a separate, orthogonal dispatch from the `n`-way fan-out below.

For the digest contract, harness-agnostic selection rules, and what the parent never delegates, see `sub-agent-gate.md`.

## Lens fan-out mode (n>1)

Activates on the router predicate above (`n>1` and `/age` not itself a sub-agent). One worker per **lens** in the router's returned `lenses` list — not per single dimension — dispatch exactly `len(lenses)` workers. The base ladder's lens partitions at `n>1`, before any override promotion:

- `n=2` — `[correctness, spec, assertions, security, telemetry]` / `[encapsulation, complexity, deslop, nih, efficiency]`.
- `n=5` — the five cohesion-grouped lenses: `[correctness, spec, assertions]`; `[security, telemetry]`; `[encapsulation, complexity]`; `[deslop, nih]`; `[efficiency]`.

An override promotion (mechanics above) pulls its mapped dimension out of whichever group the base tier placed it in and gives it its own solo lens; the group's remaining members survive as one lens together. Every grouping above is chosen for thematic cohesion — `encapsulation` never shares a lens with `efficiency` or `telemetry` at `n=5`.

The seam sequence below is identical for every `n>1` — only worker count and each worker's assigned dimension set vary with `n`:

**Seam 1 — Predicate.** As defined at the section opener above.

**Seam 2 — Shared context packet.** The orchestrator assembles the packet once, writes it to `.cheese/age/<slug>-packet.md`, and each worker reads it. Eight components, and the reuse of the review-context digester as the orientation block, are documented in `packet.md`.

**Seam 3 — Worker contract.** One worker per lens. Resolve the `reviewer` role through `../../cheese/references/agent-resolution.md` at the router's `effort` dial; require read-only permissions and fresh context, a prompt-constrained general fallback allowed only with `degraded: true`. Each worker:
- Reviews every dimension in its assigned lens (a solo-lens worker reviews just that one dimension; a multi-dimension lens worker reviews all dimensions in its group, e.g. the `[correctness, spec, assertions]` worker reviews all three).
- Computes **full per-finding severity** for every dimension in its lens (base + location bump + compounding bump).
- Tags each finding with its dimension and an `also-relevant-to: [<dim>, ...]` field when cross-dimension overlap is suspected (including overlap with a dimension owned by a *different* lens).
- Reports every defect it notices, however minor — no severity-conservative self-filtering; the verifier pass (Seam 6) and orchestrator reconciliation (Seam 4) do the filtering.
- Returns full per-finding rows in the `SKILL.md § Output` finding format (`**[dim:sev]** path:line — claim` + `location / fix-cost-now / fix-cost-later / confidence` + `recommendation`). Not an orientation digest — the `§ Digest contract` size ceiling does not apply.
- Does **not** dedup, apply boundary tiebreakers, reconcile severity across dimensions or lenses, or write the report.

After all workers return, continue at Seam 4 (reconciliation) below.

**Seam 4 — Orchestrator reconciliation.** After all workers return, apply the `## Dimension boundaries` table (`dimensions.md` § Dimension boundaries) verbatim to any line meeting EITHER condition: (1) flagged by two or more workers at the same `file:line`; (2) tagged `also-relevant-to: [d]` by any worker — the orchestrator re-evaluates dimension `d` against that line and applies the tiebreaker (keep the higher-base finding / suppress / emit-both-with-cross-reference per the 15 rules). This consumes the `also-relevant-to` signal and provides the cross-dimension coverage single-parent gets for free. Lines neither flagged by ≥2 workers nor tagged `also-relevant-to` need no reconciliation. Group by severity. The parent owns the canonical artifact. After reconciliation, continue at Seam 6 (verifier pass), then step 5 (write + print the report path) and `SKILL.md § Handoff` exactly as the single-parent path does.

**Seam 5 — Shared impact evidence.** The packet carries the caller/dependency notes assembled through `tilth_deps` and the selected semantic caller search. Workers use that packet instead of rebuilding impact context independently.

**Seam 6 — Verifier pass.** After Seam 4 reconciliation produces the candidate findings list, a cheap `verifier` role (haiku/tiny tier, `effort: low` per the Roles x tiers table) checks each reconciled finding against the evidence slice cited in its `recommendation`/location fields — one verifier call per finding, schema-constrained to "verify exactly one claim." Three outcomes:
- **Confirm** — the cited evidence supports the claimed severity; the finding ships unchanged.
- **Downgrade/drop** — the evidence does not support the claimed severity (or the claim itself); the verifier lowers the severity tier or drops the finding, and the orchestrator records the original claim and the verifier's reasoning in the report's confidence trail.
- **Escalate** — the evidence given cannot settle the claim either way (cross-cutting contract 1: "a claim no evidence can settle returns `escalate`, never a guessed pass or fail"). The finding is kept at its **original** severity with an `escalate` flag — never silently dropped or silently passed through unflagged.

This is the "cheap severity-filter leg" referenced in the Roles x tiers table; it applies whenever `n>1`. It does not run at `n=1` — the single-parent path has no reconciliation step to filter, and the reviewer's own severity computation is the only grading pass.

**Output shape invariant.** The findings report (`.cheese/age/<slug>.md`) has the same dedup, severity grouping, and finding format in the single-parent path and every lens fan-out width. Resolution provenance may expose the selected role and topology.
