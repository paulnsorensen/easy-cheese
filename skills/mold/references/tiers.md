# Tiers — scale the ceremony to the job

Mold picks a tier at the end of the Bounds pass (`../SKILL.md` Flow step 1), once the goals, non-goals, and shape-check verdict are on the ledger. Announce the tier in one line with its reason before the first fork question:

```text
tier: quick — clarity check passed, verdict low, no open fork
```

The user overrides with the `quick`, `light`, or `full` knob at any time. Mold upgrades on its own when the evidence changes. It never downgrades silently.

## The three tiers

| Tier | Enter when every condition holds | Runs | Skips | Artifact → handoff |
| --- | --- | --- | --- | --- |
| **Quick** | Cook's standalone fast-path check passes on the bounded ask ([`../../cook/SKILL.md`](../../cook/SKILL.md) § Standalone fast-path); shape-check verdict `low`, or skipped as greenfield or a single private function; no consequential fork open after bounds | Bounds, one wiki probe, one fast confirm (`go`, `yes`, `ship it`) | Explore, Shape, Sketch, Grill, Validate and Prototype cycles, fork taste test, typed planner, handshake checklist, ADRs, follow-up publication | mini-spec through [`mini-spec-mode.md`](mini-spec-mode.md), still gated by `validate-spec --strict` → `/cook --auto <spec-path>` |
| **Light** | Goal is clear after bounds; verdict `low` or `medium`; at most two consequential forks; no new public seam across modules; one expected curd | Bounds, Ground, Shape for the open forks, Sketch only when a public seam changes, fork taste test, two-key handshake, Curdle phase one | Explore; Grill unless the user asks or a fork turns high-blast; typed planner and `publish` (one curd needs no `CurdPlan`); issue-draft publication | full spec (`source: mold-handshake`) → `/cook --auto <spec-path>` |
| **Full** | Anything else: verdict `high` or `[?]`, three or more forks, a new cross-module public seam, two or more expected curds, a Diagnose input, or the `full` knob | The whole Flow | Nothing | spec + `PlannerResult` + `CurdPlan` → `mold.pyz publish` pointer → `## Handoff` menu |

The fast confirm is Quick's user key and `validate-spec --strict` is its agent key. The checklist in [`handshake.md`](handshake.md) applies to Light and Full only. Light marks each handshake box that does not apply as `n/a: <reason>` out loud rather than leaving it unchecked. `curdle anyway` is never needed to leave a gate that was never entered.

## Upgrade rules

Upgrade the moment any condition breaks. Announce the new tier with its trigger and keep every ledger entry.

- A consequential fork opens after Quick's confirm → Light. The confirm is void until the fork is picked.
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

## Relationship to `/cheese`

`/cheese` enters mini-spec mode directly at its tier 1 with no confirm, because the clarity check already passed on the raw input. Mold's Quick tier is the same mode entered from a user invocation, with one confirm because the user chose to talk first. A `mold` intent from `/cheese` still lands in user mode and tiers itself here.
