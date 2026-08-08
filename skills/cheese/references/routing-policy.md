# Subagent routing policy

> **Provenance:** this file mirrors the wiki-canonical page `architecture/subagent-routing-policy.md` (corpus `repo:dotfiles:wiki` — see `.hallouminate/wiki/architecture/subagent-routing-policy.md` once that page exists). The wiki copy is authoritative; this copy exists so easy-cheese skills can reference routing policy without a wiki round-trip. If the two diverge, the wiki wins — drift should be checked (drift-check tooling is dotfiles-side `/harness-doctor` work, out of scope for this file) and this mirror updated to match.
>
> Source spec: `subagent-routing-overhaul.md` PR1 workstream item 7.

## Goal

Each pipeline entry point sizes its own work at the moment its evidence is free; model tier follows phase; reviewer and coder count scale with size and risk. There is no universal scoper stage: sizing evidence is a byproduct of each phase (mold has the dialogue, cook has the spec, age has the diff, affinage has the PR, pasteurize has the symptom). Strong models spend only at serial bottlenecks (the spec freeze and the fresh review); workers run inside frozen contracts at worker tier.

## The four sizing functions

| Entry | Free evidence | Decision | Output |
|---|---|---|---|
| mold gate | the design dialogue | full spec vs small behavior; tier check | spec-sized: warn to upgrade (harness-detected phrasing: claude `/model opus` + `/effort`; codex/OMP named equivalent; generic fallback), then dispatch the fresh-context decomposer on draft spec text; curds land in the approved artifact. small: mini-spec fast path at current tier |
| cook gate | the spec (curd block, else AC count and edit-site estimate) | single vs fan vs decompose-first; wave plan; transport | curds present: fan in waves of <=4. un-curded: small goes single coder; big dispatches the same decomposer, then gates ("12 ACs -> 5 curds, 2 waves, up to 25 agent dispatches. Go?") |
| age router | review-surface score + risk-flag grep (affinage: comment count + CI failure class) | N and effort | N in {1 all-dims, 2 grouped, 5 lenses} + effort dial (fast pass low/medium per Opus 5); overrides promote a dimension to a solo lens rather than pushing N up |
| pasteurize gate | symptom shape + review-surface score over the suspect range | shallow vs deep; fan width | fan width 1/2 (regression, tight/wide range) or 3 (heisenbug/race/perf-regression) or 3-5 (cold bug, no diff to anchor to) via `src/fanout/pasteurize_route.py`; clean stack trace + deterministic repro: stay at current tier. heisenbug, race, cross-module, perf regression: warn-upgrade before hypothesis formation |

## Roles x tiers (all three harnesses)

| Role | claude | codex | OMP | effort | notes |
|---|---|---|---|---|---|
| explorer | sonnet | terra | task | low (from medium) | judgment-shaped digests stay sonnet (KG playbook Table IV doctrine); haiku fits only schema-constrained scans |
| researcher | sonnet | terra | (researcher agent) | medium | unchanged |
| coder | sonnet | terra | task | medium | gains ESCALATE contract; delegation IS the downgrade |
| verifier | haiku | luna | tiny | low | "verify exactly one claim"; schema-constrained; the cheap severity-filter leg |
| reviewer | opus | sol | slow | dial: low/medium fast pass, high thorough | pinned strong; count and effort follow the age router |
| planner / integrator | orchestrator | orchestrator | plan/default | xhigh at mold | never delegated; owns approval loop |

Scoper: deleted everywhere.

## Hard risk-overrides

Any one of the following forces strong review and lowers mold's spec bar, regardless of size:

- auth/secrets/crypto/tenant isolation
- payments/ledgers/irreversible effects
- concurrency/idempotency/ordering/retries
- schema/migration/protocol/public-API change
- production-destructive ops
- weak integration coverage around a global invariant

## Cross-cutting contracts

1. **Grounded verdicts** — every reviewer dispatch (age lens, taste, affinage triage) carries the evidence slice it checks against (diff hunks, spec lines, test output) and must cite it in each verdict; a claim no evidence can settle returns `escalate`, never a guessed pass or fail.
2. **Report-everything reviewers** — severity-conservative phrasing is banned in reviewer prompts; filtering happens in the reconcile/verifier pass (Opus 5 recall behavior).
3. **Fan-in envelope** — fixed schema, `status`/`next`/`artifact`/orientation plus SCOPE (owned/untouched), EVIDENCE, ASSUMPTIONS, RISKS. Workflows validate the envelope mechanically (validation is not routing; thin-wrapper rule holds). See `handoff-gate.md` § Fan-in envelope fields for the documented schema.
4. **Delegation restraint** (Opus 5 orchestrators) — delegate only genuinely independent, sizeable tracks; never spawn agents to verify your own work (cheaper-writer checks, opus reviewer over sonnet coder, stay); one agent when one suffices; no delegation for handful-of-tool-call work.
