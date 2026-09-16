# Sub-agent context gate (shared kernel)

These cross-skill rules govern work that a skill sends to a sub-agent.

Each skill names its own triggers.
This file is the single source of truth for the rules that every skill shares.

## Digest contract

The sub-agent returns 2 KB or less of UTF-8 text.
It returns a structured summary, citations, and gaps.
It returns no raw bodies, no full file dumps, and no copied source text.
Each skill names the digest contents, such as a claim table, an orientation paragraph, or a root-cause summary.
One exception exists. An Age subject worker returns full per-finding rows without a size ceiling.
`fan-out.md` § Dispatch and shared evidence defines that worker.
The ceiling applies to every other sub-agent.

## Harness-agnostic sub-agent selection

Resolve every worker through [`../../cheese/references/agent-resolution.md`](../../cheese/references/agent-resolution.md).
The calling skill supplies the work, permission/isolation floor, minimum power, effort, and fallback.
This context kernel governs only digest boundaries.

## What the parent never delegates

By default, the parent never delegates severity grading, final verdicts, or approval gates.
Age may delegate candidate grading to subject workers across every dimension their assigned investigation exposes.
The parent retains cross-subject reconciliation, verification, final verdicts, and canonical report writing.
This exception does not loosen the default for other cases.

Do not delegate dialogue, contradictions, handshakes, or user-facing decisions.
Do not delegate writing the canonical artifact (report, spec, claim table).
The sub-agent supplies the digest; the parent writes the document.

## What the sub-agent owns

The sub-agent owns bulk fetches, extracts, crawls, and multi-source research.
It owns many-file reads and dependency / caller graph traversals.
For code navigation, start with `kind:symbol` to find the definition.
Then use `kind:callers` for call sites.
Fall back to `content`/`regex` only when you do not have a symbol name.
It also owns work that yields mostly raw bodies that the parent will not read line by line.
Send the work to a sub-agent when the raw output is more than 5000 tokens.

## Parallelism

When two or more heavy units of work are independent, spawn one small sub-agent per unit in parallel.
Merge the digests in the parent.
Do not send one sub-agent to do five sequential tasks; that shape is wrong.

## Age router as fan-out predicate

`/age` sizes its fan-out with the age router, not with a size-only threshold.
`skills/age/SKILL.md § Sub-agent fan-out` uses `route(context=...)` in `src/easy_cheese/shared/fanout/age_route.py`.
The router assigns subjects from evidence, effort, workload, and execution capabilities.
`fan-out.md` owns the context and assignment contract. This file does not repeat it.
This file's digest contract, selection rules, and delegation boundaries apply to every worker that the router starts.
