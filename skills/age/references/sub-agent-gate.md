# Sub-agent context gate (shared kernel)

Cross-skill rules for forking work to a sub-agent. Adopted from Anthropic's effective-context-engineering guidance, Tavily's published skills, and the cross-harness norms used by LangChain DeepAgents and the Skills standard.

Each skill names its own triggers. This file is the single source of truth for the things every skill agrees on.

## Digest contract

The sub-agent returns roughly 2 KB or less: structured summary, citations, gaps. No raw bodies, no full file dumps, no copy-paste of fetched content. Skills name what the digest contains — claim table, orientation paragraph, root-cause summary, etc. — but never relax the size ceiling.

## Harness-agnostic sub-agent selection

Resolve every worker through [`../../cheese/references/agent-resolution.md`](../../cheese/references/agent-resolution.md). The calling skill supplies the work, permission/isolation floor, minimum power, effort, and fallback; this context kernel only governs digest boundaries.
## What the parent never delegates

- Severity grading, final verdicts, approval gates. **Exception (scope-limited):** a skill may delegate single-dimension grading to a per-dimension worker **iff** the parent retains final cross-dimension reconciliation and the verdict — the verdict and the cross-cutting grade stay central. This exception does not loosen the default for any other case.
- Dialogue, contradictions, handshakes, user-facing decisions.
- Writing the canonical artifact (report, spec, claim table) — the sub-agent supplies the digest; the parent writes the doc.

## What the sub-agent owns

- Bulk fetches, extracts, crawls, multi-source research.
- Many-file reads, dependency / caller graph traversals. For code navigation, start with `kind:symbol` to find the definition, then `kind:callers` for call sites. Fall to `content`/`regex` only when you don't have a symbol name.
- Anything yielding mostly raw bodies that the parent will not read line by line — about 5 K tokens of raw output is the industry rule of thumb for "fork it".

## Parallelism

When two or more heavy units of work are independent, spawn one small sub-agent per unit in parallel and merge their digests in the parent. One sub-agent doing five things sequentially is the wrong shape.
