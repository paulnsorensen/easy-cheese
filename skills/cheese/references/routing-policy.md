# Subagent routing policy

> **Provenance:** This file mirrors `architecture/subagent-routing-policy.md` in `repo:dotfiles:wiki`.
> The wiki copy is authoritative.
> This mirror lets easy-cheese use the policy without a wiki request.
> When they differ, update this mirror to match the wiki.
> Use `/harness-doctor` to check drift.
> Source specification: `subagent-routing-overhaul.md` PR1 workstream item 7.

## Goal

Each pipeline entry point sizes its own work when its evidence is available.
The phase selects the model tier.
Size and risk select reviewer and coder counts.
Each phase produces its own size evidence.
No universal scoper stage exists.
Use strong models only at serial bottlenecks.
Workers use frozen contracts at worker tier.

## The four sizing functions

| Entry | Free evidence | Decision | Output |
|---|---|---|---|
| mold gate | the design dialogue | full spec vs small behavior; tier check | spec-sized: warn to upgrade (harness-detected phrasing: claude `/model opus` + `/effort`; codex/OMP named equivalent; generic fallback), then dispatch the fresh-context decomposer on draft spec text; curds land in the approved artifact. small: mini-spec fast path at current tier |
| cook gate | the spec (curd block, else AC count and edit-site estimate) | single vs fan vs decompose-first; wave plan; transport | curds present: fan in waves of <=4. un-curded: small goes single coder; big dispatches the same decomposer, then gates ("12 ACs -> 5 curds, 2 waves, up to 25 agent dispatches. Go?") |
| age router | review-surface score + risk-flag grep (affinage: comment count + CI failure class) | N and effort | N in {1 all-dims, 2 grouped, 5 lenses} + effort dial (fast pass low/medium per Opus 5); overrides promote a dimension to a solo lens rather than pushing N up |
| pasteurize gate | symptom shape + review-surface score over the suspect range | shallow vs deep; fan width | fan width 1/2 (regression, tight/wide range) or 3 (heisenbug/race/perf-regression) or 3-5 (cold bug, no diff to anchor to) via `src/easy_cheese/shared/fanout/pasteurize_route.py`; clean stack trace + deterministic repro: stay at current tier. heisenbug, race, cross-module, perf regression: warn-upgrade before hypothesis formation |

## Roles x tiers (all three harnesses)

| Role | claude | codex | OMP | effort | notes |
|---|---|---|---|---|---|
| explorer | sonnet | terra | task | low (from medium) | judgment-shaped digests stay sonnet (KG playbook Table IV doctrine); haiku fits only schema-constrained scans |
| researcher | sonnet | terra | (researcher agent) | medium | unchanged |
| coder | sonnet | terra | task | medium | gains ESCALATE contract; delegation IS the downgrade |
| verifier | haiku | luna | tiny | low | "verify exactly one claim"; schema-constrained; the cheap severity-filter leg |
| reviewer | opus | sol | slow | dial: low/medium fast pass, high thorough | pinned strong; count and effort follow the age router |
| planner / integrator | orchestrator | orchestrator | plan/default | high at mold | never delegated; owns approval loop |

Scoper: deleted everywhere.

## Hard risk-overrides

Any listed condition requires strong review and lowers mold's specification threshold:

- auth/secrets/crypto/tenant isolation
- payments/ledgers/irreversible effects
- concurrency/idempotency/ordering/retries
- schema/migration/protocol/public-API change
- production-destructive ops
- weak integration coverage around a global invariant

## Cross-cutting contracts

1. **Grounded verdicts** — each reviewer receives the evidence slice for its check.
   Each verdict cites diff hunks, specification lines, or test output.
   Return `escalate` when evidence cannot settle a claim.
2. **Report-everything reviewers** — severity-conservative phrasing is banned in reviewer prompts; filtering happens in the reconcile/verifier pass (Opus 5 recall behavior).
3. **Fan-in envelope** — fixed schema, `status`/`next`/`artifact`/orientation plus SCOPE (owned/untouched), EVIDENCE, ASSUMPTIONS, RISKS. Workflows validate the envelope mechanically (validation is not routing; thin-wrapper rule holds). See `handoff-gate.md` § Fan-in envelope fields for the documented schema.
4. **Delegation restraint** — delegate only independent and substantial tracks.
   Do not delegate verification of your own work.
   Use one agent when one is sufficient.
   Do not delegate work that needs only a few tool calls.
