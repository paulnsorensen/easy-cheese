# Ultracook agent topology (now owned by /cook's fan pathway)

> **Ownership moved (2026-07-24, PR #316; retirement PR #317):** `/cook`
> absorbed this topology — mode selection, milknado seam, phase-chain ordering,
> deterministic phase loop, worker-exhaustion/aggregate-gate recovery, worktree
> lifecycle, resolution provenance, baseline capture, and `--resume` — into its
> single **Fan pathway** (`skills/cook/SKILL.md § Fan pathway`). `/ultracook`
> was then retired to a redirect stub in PR #317. The invariants below still
> hold; only the owning skill changed.

The fan pathway assigns a fresh typed agent to each reasoning phase instead of
running a whole curd through one write-capable worker.

## Phase ownership

- Decomposition uses a planner or compatible general worker.
- Seed, cook, press, cure, and wiring use a coder.
- Every age pass uses an independent reviewer.
- Harvest and plate remain parent-orchestrator responsibilities.[^1]

Each curd runs Cook, then independent Age review in its isolated worktree.
Confirmed diagnosis permits Cure, followed by another Age review.
A curd does not run Press while sibling curds remain incomplete.
The post-merge scope starts with Press, then Age.
Each post-merge Cure runs Press before the next Age review.[^2]

The progress-aware state machine stops on clean coverage, stalled debt, invalid evidence, or a new gate failure.
Only complete curd coverage and a clean post-merge scope permit `next: done`.[^5]

## Reproducible review identity

The live runtime binds each scope to its run identifier, scope kind, scope identifier, and source-plan reference.
A curd named `postmerge` remains distinct from the post-merge scope.
Review and Cure observations carry request identity and the locked finding selection.
`run_fan` owns semantic transitions; the legacy manifest is not workflow authority.[^5]

## Crash-safe remediation

One nonblocking OS lock protects each run.
The lock spans adapter preflight, manifest writes, semantic transitions, and final publication.
Standalone `run_fan` acquires its own lock; the adapter uses the documented already-locked entry.[^6]
The lock file remains present; process exit releases ownership without a stale-PID deletion race.[^6]

Resume retains validated initial Press references when no new Press call occurs.
Repeated resumes must not erase that evidence from the manifest.[^9]

Before Cure dispatch, the host records the exact intent.
After dispatch, it records the completed worker observation before publishing the transition.
Resume reuses only a completed observation with matching scope, round, selection, and request identity.
A prepared intent without that observation blocks as outcome-unknown.
It never claims that selected findings were applied.
Post-merge Press still runs after replay.[^7]

Automatic selection includes critical, high, medium, and contained-low findings.
Other low findings remain recorded but excluded from automatic debt.
`FixCostNow.MODERATE` remains a valid cost class; it does not widen low selection.[^8]

## Why

The previous parallel worker performed cook, press, age, and cure in one
context, so review was not independent and cure could modify code after the
last review. Post-merge review also lacked a reproducible diff identity. Typed
top-level phases and a mandatory final age close both publication paths.

The `/ultracook` → `/cook` consolidation moved fan-path ownership in PR #316
and retired the duplicate `/ultracook` entry point in PR #317: one skill now
owns both the linear and fan pathways, choosing by the same decompose gate, so
mode selection is a routing decision inside `/cook` rather than a skill choice
the user makes up front.

Related decision: [progressive agent resolution](../adr/agent-resolution.md).

[^1]: skills/cook/SKILL.md § Fan pathway (moved from skills/ultracook/SKILL.md in PR #316; the old skill retired to a redirect stub in PR #317)
[^2]: skills/cook/references/fan-pathway.md:56-120; src/easy_cheese/shared/fanout/run_fan.py:531-726.
[^5]: src/easy_cheese/shared/fanout/run_fan.py:185-212,842-1011.
[^6]: src/easy_cheese/shared/advisory_lock.py; src/easy_cheese/shared/fanout/remediation_store.py:run_lock; src/easy_cheese/skills/cook/preparation/fan_execute.py:execute_fan; src/easy_cheese/shared/fanout/run_fan.py:run_fan_locked.
[^7]: src/easy_cheese/shared/fanout/run_fan.py:348-452,597-683.
[^8]: src/easy_cheese/shared/fanout/remediation.py:95-144; src/easy_cheese_schemas/contracts.py:FixCostNow.
[^9]: src/easy_cheese/skills/cook/preparation/fan_execute.py:_execute_fan_locked; tests/python/test_cook_execution.py:test_press_resume_requires_manifest_refs.

_Source: PR #316 ownership and PRs #701–#708 remediation cure · Updated: 2026-09-20 · Supersedes: per-curd Press and legacy manifest authority in the 2026-07-24 description_
