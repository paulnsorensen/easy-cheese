# Tiers — scale the ceremony to the job

Mold picks a tier at the end of the Bounds pass (`../SKILL.md` Flow step 1), once the goals, non-goals, and shape-check verdict are on the ledger. Announce the tier in one line with its reason before the first fork question:

```text
tier: quick — clarity check passed, verdict low, no open fork
```

The user overrides with the `quick`, `light`, or `full` knob at any time. Mold upgrades on its own when the evidence changes. It never downgrades silently.

## The three tiers

| Tier | Enter when every condition holds | Runs | Skips | Artifact → handoff |
| --- | --- | --- | --- | --- |
| **Quick** | Cook's standalone fast-path check passes on the bounded ask ([`../../cook/SKILL.md`](../../cook/SKILL.md) § Standalone fast-path), which includes zero fired leverage triggers ([`../../cheese/references/routing-policy.md`](../../cheese/references/routing-policy.md) § Leverage triggers); shape-check verdict `low`, or skipped as greenfield or a single private function; no consequential fork open after bounds | Bounds, one wiki probe, strict mini-spec validation | Explore, Shape, Sketch, Grill, Validate and Prototype cycles, fork taste test, typed planner, full coherence checklist, ADRs, follow-up publication | draft mini-spec through [`mini-spec-mode.md`](mini-spec-mode.md), gated by `validate-spec --strict`; finalize and hand Cook a canonical `HandoffPointer` only after the user requests Cook |
| **Light** | Goal is clear after bounds; verdict `low` or `medium`; at most two consequential forks; no new public seam across modules; one expected curd | Bounds with `G-n` clauses, Ground, Shape for the open forks, Sketch only when a public seam changes, fork taste test, goal coverage and narrowing delta, agent coherence check, Curdle draft write | Explore; Grill unless the user asks or a fork turns high-blast; typed planner (one curd needs no `CurdPlan`); issue-draft publication | draft full spec (`source: mold-handshake`); after a user Cook request, finalize and hand Cook the canonical `HandoffPointer` |
| **Full** | Anything else: verdict `high` or `[?]`, three or more forks, a new cross-module public seam, two or more expected curds, a Diagnose input, or the `full` knob | The whole Flow, including early curd checks when one becomes concrete | Nothing | draft spec + validated `PlannerResult` + `CurdPlan`; after a user Cook request, finalize the exact scope and offer the canonical `HandoffPointer` |

A fired leverage trigger rules Quick out: the fork it names is consequential, so the ask enters Light or Full by the rows above. Leverage picks whether the user steers; the verdict, fork count, and curd count pick how much of the Flow runs.

`validate-spec --strict` is Quick's write gate. The coherence checklist in [`handshake.md`](handshake.md) applies to Light and Full before a runnable handoff. Light marks each box that does not apply as `n/a: <reason>`. No tier treats spec writing as Cook consent.

## Upgrade rules

Upgrade the moment any condition breaks. Announce the new tier with its trigger and keep every ledger entry.

- A consequential fork opens after Quick's bounds pass → Light. Keep the saved mini-spec as draft until the fork is picked.
- The shape-check verdict rises to `high` or `[?]` → Full, Grill mandatory.
- A second module or a new public seam enters scope → Full.
- The expected curd count reaches two → Full. The typed planner is required.
- Cook returns `next: mold` on a Quick mini-spec → re-enter at Light with Cook's failure as prior evidence.

Downgrade only on the user's knob. Say what the lower tier skips before continuing.

## What no tier skips

- The wiki probe and its ledger record (`grounding-recorded`).
- The agent-introduced-scope check: every distinguishing noun traces to the user's words.
- `validate-spec --strict` on whatever artifact ships.
- The user's say on every consequential fork.
- The leverage-trigger check: a fired trigger never lands in Quick.

## Relationship to `/cheese`

`/cheese` enters mini-spec mode directly at tier 1 when the clarity check passes. Mold's Quick tier writes the same validated draft without a separate approval turn. A `mold` intent from `/cheese` still enters user mode and tiers itself here. An original request to Cook can supply execution consent; a request to design cannot.
