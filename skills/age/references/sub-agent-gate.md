# Sub-agent context gate (shared kernel)

These cross-skill rules govern work that a skill forks to a sub-agent.
Anthropic's effective-context-engineering guidance, Tavily's published skills, and cross-harness norms from LangChain DeepAgents and the Skills standard informed them.

Each skill names its own triggers.
This file is the single source of truth for the rules that every skill shares.

## Digest contract

The sub-agent returns roughly 2 KB or less.
It returns a structured summary, citations, and gaps.
It returns no raw bodies, full file dumps, or copy-paste of fetched content.
Each skill names the digest contents, such as a claim table, orientation paragraph, or root-cause summary.
The size ceiling never relaxes.

## Harness-agnostic sub-agent selection

Resolve every worker through [`../../cheese/references/agent-resolution.md`](../../cheese/references/agent-resolution.md).
The calling skill supplies the work, permission/isolation floor, minimum power, effort, and fallback.
This context kernel governs only digest boundaries.

## What the parent never delegates

By default, the parent never delegates severity grading, final verdicts, or approval gates.
A skill may delegate single-dimension grading to a per-dimension worker only when the parent retains final cross-dimension reconciliation and the verdict.
The verdict and cross-cutting grade stay central.
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
Use about 5 K tokens of raw output as the industry rule of thumb for "fork it".

## Parallelism

When two or more heavy units of work are independent, spawn one small sub-agent per unit in parallel.
Merge the digests in the parent.
Do not send one sub-agent to do five sequential tasks; that shape is wrong.

## Age router as fan-out predicate

`/age` and `/affinage` through it no longer use a size-only threshold to decide fan-out.
`skills/age/SKILL.md § Sub-agent context gate` calls `src/easy_cheese/shared/fanout/age_route.py`'s `route(score=...)`.
The router forks according to its `n` value (1 / 2 / 5).
This file's digest contract, selection rules, and delegation boundaries still apply to every worker that the router spawns.
