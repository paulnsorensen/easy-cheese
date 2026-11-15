# Fan-out gating units: what frameworks, measurements, and prior art support

No surveyed framework gates fan-out on input size. Every one gates on a runtime budget. No published measurement gives a transferable "best N" of sub-agents. Prior art says to unify thresholds into one score only when the score feeds one decision from measured inputs. Prior art also says to instrument first and derive constants later.

Research ran on 2026-07-27 with web search and page extraction against primary vendor documentation and papers. Confidence markers: `<certain>` means a primary source states it. `<speculative>` means this page infers it. `<don't know>` means the sources checked do not answer it.

## What this means for ADR-005

[ADR-005](../adr/deterministic-fanout-sizing-005.md) leaves "the size score and its inputs" to a follow-up `/mold`. Four findings bear on that work:

1. **No off-the-shelf size gate exists.** The size score is new design. No framework default (`max_iter=20`, `recursion_limit=25`) transfers to it. Each of those defaults is a runtime budget with no published derivation.
2. **Keep runtime budgets as separate gates.** Concurrency caps, turn caps, and retry caps stay useful beside the size score. The frameworks use them for runaway control, which a size score does not provide.
3. **Token cost is the best-supported input.** Token usage explains 80% of performance variance in one Anthropic eval. A multi-agent run costs about 15x a plain chat. A size score that estimates tokens has measured backing. A score built from file counts alone has none.
4. **Return per extra worker flattens, and coding fits fan-out poorly.** The curve supports a low parallel ceiling and a bias toward inline or one-worker cooking. The measured curves come from sampling and judging tasks, so treat them as shape evidence only.

Prior art adds two rules for the score itself. See "Unify or keep separate" and "Instrument first" below.

## Frameworks gate on runtime budget

`<certain>` for every row below. The unit column shows what each framework counts.

| Framework | Knob | Unit | Default |
| --- | --- | --- | --- |
| Claude Agent SDK | `max_turns` | turn count | none; the caller sets it |
| Claude Code subagents | `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` | nesting depth | 3 in v2.1.219 and later; changed across versions |
| Claude Code workflows | concurrent-agent cap | agent count | `min(16, cpu_cores - 2)` |
| Claude Code workflows | total-agent cap | agent count per run | 1,000 |
| OpenAI Agents SDK | `max_turns` | turn count | no number; `None` disables the cap |
| LangGraph | `recursion_limit` | super-step count | 25 |
| LangGraph | `max_concurrency` | concurrent steps | unset (unbounded in a super-step) |
| LangGraph | `Send` | fan-out width computed by the caller | not a cap |
| CrewAI | `max_iter` | iteration count | 20 |
| CrewAI | `max_rpm`, `max_execution_time` | rate, wall-clock seconds | unset |
| AutoGen/AG2 | `max_round`, `max_consecutive_auto_reply` | round and reply counts | no documented number; examples set 6 to 12 |

Sources: [Claude Code subagents](https://code.claude.com/docs/en/agent-sdk/subagents), [Claude Code workflows](https://code.claude.com/docs/en/workflows), [anthropics/claude-code#63938](https://github.com/anthropics/claude-code/issues/63938), [OpenAI Agents SDK run reference](https://openai.github.io/openai-agents-python/ref/run), [LangGraph recursion limit](https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT), [CrewAI agents](https://docs.crewai.com/v1.15.5/en/concepts/agents), [AG2 FAQ](https://docs.ag2.ai/latest/docs/user-guide/FAQ), [AG2 GroupChat](https://docs.ag2.ai/latest/docs/user-guide/advanced-concepts/groupchat/groupchat).

Findings:

- Turn, concurrency, and round caps have real analogues in every framework. `<certain>`
- Diff size, file count, and an abstract 0-10 risk score have no analogue in the sources checked. `<certain>` for Anthropic, OpenAI Agents SDK, LangGraph, CrewAI, and AG2. `<don't know>` for Google ADK, smolagents, Semantic Kernel, and OpenAI Swarm. The pass did not fetch them.
- Anthropic's only complexity rule is advice in the lead agent's prompt: one agent for a simple fact, 2-4 subagents for a comparison, more than 10 for complex research. An LLM judges the complexity. Code does not enforce it. The same post says agents "struggle to judge appropriate effort". See [the multi-agent research system post](https://www.anthropic.com/engineering/multi-agent-research-system). `<certain>`
- Most defaults are asserted, not measured. The Claude Code `16` cap derives from host CPU cores, not from a workload measurement. No primary source explains `max_iter=20` or `recursion_limit=25`. `<certain>` that none was found in the pages fetched. `<speculative>` on why those numbers exist.

## Measured evidence on sub-agent counts

No source supports a universal "best N". The evidence shows the shape of the curve. `<certain>` for each cited benchmark.

| Claim | Number | Source | Scope |
| --- | --- | --- | --- |
| Multi-agent costs more tokens than chat | about 15x chat; a single agent about 4x | [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system) | production telemetry |
| Multi-agent beats one agent | +90.2% | same | internal research eval; method not public |
| Token usage explains performance variance | 80% alone; 95% with tool calls and model | same | BrowseComp regression |
| More self-consistency samples help little on strong models | +0.4% (HotpotQA, 20 samples), +1.6% (MATH-500) | [arXiv 2511.00751](https://arxiv.org/html/2511.00751v2) | Gemini 2.5; declines at high N in some setups |
| Parallel sampling helps from K=1 to 4 | about 50% relative gain | [arXiv 2602.18998](https://arxiv.org/html/2602.18998v1) | K capped at 4 for API cost |
| Judge panels converge near 3 | 3 judges | [PoLL, arXiv 2404.18796](https://arxiv.org/abs/2404.18796) | evaluator agreement, read second-hand |

Caveats:

- Anthropic publishes no cost per extra subagent. `<don't know>` on the marginal curve.
- The K=4 cap is a cost limit. It does not show that returns flatten at 4.
- The panel-of-3 result measures judge agreement. It does not support "3 reviewers" as a fan-out count. `<speculative>` if applied to review fan-out.
- Anthropic says coding fits multi-agent poorly because of shared context and heavy dependencies. The cost multipliers do not justify wide fan-out for code.
- Cognition says to keep writes single-threaded ([Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents), [Multi-Agents: What's Actually Working](https://cognition.com/blog/multi-agents-working)). Both are practitioner reports with no numbers. `<speculative>`
- A search for coding-agent teams that report "we tried N and settled on M" found nothing. `<don't know>`: the crawl of Cursor, Sourcegraph, and Factory blogs was incomplete.

The local measurement already agrees with this shape. [Fan-out patterns 2026-09-10](../analytics/fanout-patterns-2026-09-10.md) found zero parallel bursts in 609 spawns. [Review fan-out policy comparison](./review-fanout-policy-comparison.md) covers the review-side policies.

## Unify or keep separate

No source names "many thresholds in incompatible units" as one pattern. It splits into two named problems. `<certain>` Fowler's catalog names the magic number. Xu et al. ([ESEC/FSE 2015](https://dl.acm.org/doi/10.1145/2786805.2786852)) name over-designed configuration. The combined framing is this page's inference. `<don't know>` whether a better term exists.

The dividing line from the literature:

- **Unify** when the inputs are one currency at several measurement points, and the score drives one decision. Google's error budget ([SRE book](https://sre.google/sre-book/embracing-risk)) and CPU-based admission control are examples. Little's Law ([overview](https://en.wikipedia.org/wiki/Little%27s_law)) gives a lossless conversion between rate, concurrency, and latency. `<certain>`
- **Keep separate** when the inputs are different objectives, such as cost, latency, and correctness. A weighted sum cannot reach the concave part of a Pareto front, whatever the weights ([Lin et al., NeurIPS 2019](http://papers.neurips.cc/paper/9374-pareto-multi-task-learning.pdf)). `<certain>` on the theory. `<speculative>` that it transfers to ops scores, because the paper treats optimization search spaces.
- Load-shedding designs feed several raw signals into one decision function. They do not blend the signals into one number. BBR keeps two control parameters, not one ([survey](https://www.mdpi.com/1424-8220/23/9/4431)).
- Whether the fan-out thresholds are "one currency" or "different objectives" is a judgment this research does not settle. `<speculative>`
- Chebyshev scalarization reaches the full Pareto front. It sits between one linear score and many thresholds. The sources raise it. This page does not evaluate it.

ADR-005 has one decision with three outcomes: inline, one worker, or parallel. That matches the "one decision" shape. The inputs are not one currency, though. Line count, token estimate, file overlap, and a fired risk trigger differ. A size score should log its inputs next to the result, so a reader can see which input moved.

## Instrument first

Three independent lineages replaced hand-set constants with live measurement. `<certain>` for each. `<speculative>` that the pattern holds outside these fields.

- DB2 STMM: continuous measurement "can essentially eliminate the need for hand tuning" ([Storm et al., VLDB 2006](https://www.vldb.org/conf/2006/p1081-storm.pdf)).
- JVM ergonomics: humans set pause-time and throughput goals. The runtime derives heap sizes from measurement ([JDK GC tuning guide](https://docs.oracle.com/en/java/javase/25/gctuning/ergonomics.html)).
- BBR: it computes the bandwidth-delay product from live bandwidth and round-trip time ([Cardwell et al., ACM Queue 2016](https://queue.acm.org/detail.cfm?id=3022184)).

Xu et al. also find many configuration knobs sit unused at their defaults. The exact percentage did not extract. Cite the paper, not this page, for a number.

The owner chose to change cook's shape before a baseline exists (see ADR-005, "Open design work"). These lineages favor the opposite order. The size score can still follow them. It should name its constants, log its inputs on every run, and leave room to replace a constant with a measured value. The `<speculative>` thresholds in [age-fanout-router](../architecture/age-fanout-router.md) (60 and 250) are the same kind of judgment call.

_Source: Tavily search and extraction against the URLs above,
2026-07-27 (frameworks, prior art) and 2026-07-27 to 2026-07-28 (measured
evidence) · Promoted from the PR #358 research scratch · Updated: 2026-11-15_
