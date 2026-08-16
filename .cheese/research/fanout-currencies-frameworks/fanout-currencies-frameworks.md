# Research: what units do published agent-orchestration frameworks use to gate parallelism/fan-out?

Date: 2026-07-27
Decision this supports: designing fan-out gating policy for the local agent pipeline (currently expressed in 5 "currencies": diff magnitude, turn/context budget, agent counts, round/retry caps, abstract 0-10 risk score).

## Synthesis

No shipped framework gates fan-out width or triggering on *input/task magnitude* (diff size, file count, a derived complexity score). Every framework reviewed gates on *runtime budget*: turn counts, concurrency caps, wall-clock/RPM limits, or round caps — plus one soft, prompt-embedded heuristic (Anthropic's "scale effort to query complexity," which is advisory text in a system prompt, not an enforced gate). Anthropic's engineering blog is the only source that reports *measured* justification for a budget number (token usage explains 80% of variance in one eval); every other documented default (CrewAI `max_iter=20`, LangGraph `recursion_limit=25`, AutoGen `max_round`) is asserted with no published derivation. Diff-magnitude gating and an abstract 0-10 risk score are idiosyncratic to this project — `<certain>` given the sources checked below, `<don't know>` for frameworks/vendors not reviewed (Google ADK, smolagents, Semantic Kernel, Swarm specifically — not fetched this pass).

## Evidence table

| Framework | Knob | Unit/currency | Default | Doc URL |
|---|---|---|---|---|
| Claude Agent SDK (Python/TS/Rust) | `max_turns` / `maxTurns` | turn count | none stated in fetched sources (examples show 3, 5, 12, 50 — caller-set) | https://hidekazu-konishi.com/entry/claude_agent_sdk_complete_guide.html (field summary of official docs); confirmed usage pattern via docs.rs claude-agent-sdk README and OpenObserve integration docs |
| Claude Code subagents | `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` | nesting depth (agent-layer count) | 3 layers (changed across versions: v2.1.172–216 was 5 and fixed; v2.1.217–218 was 1; v2.1.219+ raised to 3) | https://code.claude.com/docs/en/agent-sdk/subagents |
| Claude Code dynamic workflows | concurrent-agent cap | agent count (concurrency) | `min(16, cpu_cores - 2)` concurrent | https://code.claude.com/docs/en/workflows |
| Claude Code dynamic workflows | total-agent cap | agent count (cumulative, "prevents runaway loops") | 1,000 agents per run | https://code.claude.com/docs/en/workflows |
| Anthropic multi-agent research system (engineering blog, not an SDK — describes their production architecture) | lead-agent subagent spawn width | agent count | "3-5 subagents in parallel" | https://www.anthropic.com/engineering/multi-agent-research-system |
| " | subagent tool-call parallelism | tool-call count | "3+ tools in parallel" per subagent | same URL |
| " | prompt-embedded effort-scaling rule (NOT an enforced gate — advisory text in the lead agent's system prompt) | tool-call count, bucketed by qualitative task complexity | simple fact-finding: 1 agent, 3-10 calls; direct comparisons: 2-4 subagents, 10-15 calls each; complex research: >10 subagents, clearly divided | same URL |
| OpenAI Agents SDK (Python) | `max_turns` (param to `Runner.run`/`run_sync`/`run_streamed`) | turn count | not documented as a numeric default; `None` disables the limit (i.e., framework ships with no cap unless caller sets one — `<certain>` this is a bounded claim: no default number found in `Runner.run` reference or `MaxTurnsExceeded` docs, only the disable value) | https://openai.github.io/openai-agents-python/ref/run and https://openai.github.io/openai-agents-python/running_agents |
| OpenAI Agents SDK | handoffs | not a numeric budget — a graph-topology mechanism (agent-to-agent control transfer); no built-in concurrency/fan-out cap found in fetched docs | n/a | https://github.com/openai/openai-agents-python/issues/123 (community confirms no built-in parallel-handoff primitive; parallelism must be hand-coded via parallel tool calls) |
| LangGraph | `recursion_limit` (RunnableConfig) | step/super-step count | 25 | https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT ; also https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/_internal/_config.py |
| LangGraph | `max_concurrency` (RunnableConfig) | concurrent-step count ("max number of concurrent steps to run, which also applies to parallelized steps") | not documented as a fixed default in fetched source (unset = unbounded within a super-step) | https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/_internal/_config.py |
| LangGraph | `Send(node, arg)` | fan-out mechanism — dynamically spawns N workers, one per `Send` returned; width is caller-computed (e.g., len(items)), not a framework-imposed cap | n/a (mechanism, not a budget) | https://forum.langchain.com/t/best-practices-for-parallel-nodes-fanouts/1900 ; https://docs.langchain.com/oss/javascript/langgraph/use-graph-api |
| CrewAI | `max_iter` (Agent) | iteration count ("maximum iterations before the agent must provide its best answer") | 20 | https://docs.crewai.com/v1.15.5/en/concepts/agents |
| CrewAI | `max_rpm` (Agent) | requests-per-minute (rate, not a fan-out gate — throttles LLM call rate) | unset/optional, no numeric default documented | https://docs.crewai.com/v1.15.5/en/concepts/agents |
| CrewAI | `max_execution_time` (Agent) | wall-clock seconds | unset/optional, no numeric default documented | https://docs.crewai.com/v1.15.5/en/concepts/agents |
| CrewAI | `async_execution=True` (Task) | boolean flag enabling concurrent task execution — not a magnitude/count knob; crew-level validation requires the task list end with at most one trailing async task | n/a (structural constraint, not a budget) | https://community.deeplearning.ai/t/automate-event-planning-the-crew-must-end-with-at-most-one-asynchronous-task/679677 |
| AutoGen/AG2 | `max_consecutive_auto_reply` (ConversableAgent) | consecutive-auto-reply count | not documented with a numeric default in fetched FAQ (examples in the wild set 3-5) | https://docs.ag2.ai/latest/docs/user-guide/FAQ |
| AutoGen/AG2 | `max_turns` (`ConversableAgent.initiate_chat`) | conversation-turn count between two agents | not documented with a numeric default in fetched FAQ | same URL |
| AutoGen/AG2 | `max_round` (`GroupChat`) | round count (one round = one speaker-selection + speak + broadcast cycle) | not documented with a numeric default; doc examples consistently use 6-12 explicitly set by the caller | https://docs.ag2.ai/latest/docs/user-guide/advanced-concepts/groupchat/groupchat |

## Answers to the three questions

**1. Which of our five currencies have real analogues, which are idiosyncratic?**

- Turn/context budget → real analogue everywhere: `max_turns` (Claude Agent SDK, OpenAI Agents SDK, AutoGen/AG2 `initiate_chat`), `recursion_limit` (LangGraph, counts graph steps not tokens directly). `<certain>`.
- Agent counts / concurrency caps → real analogue: Claude Code workflows (`16` concurrent / `1,000` total), LangGraph `max_concurrency`, CrewAI's async task model (boolean, not a count), Anthropic's "3-5 subagents" prompt guidance. `<certain>`.
- Round/retry caps → real analogue: AutoGen/AG2 `max_round` (GroupChat) and `max_consecutive_auto_reply` are a direct match to "corrective rounds / retries." `<certain>`.
- Diff magnitude (files/lines changed, derived score) → no analogue found in any framework reviewed. All frameworks gate on runtime behavior (turns/steps/tool-calls/time), never on a pre-computed measure of the *input's* size. `<certain>` this is unmatched among the sources fetched (Anthropic docs, OpenAI Agents SDK docs, LangGraph docs/source, CrewAI docs, AG2 docs) — `<don't know>` for frameworks not reviewed this pass (Google ADK, smolagents, Semantic Kernel, OpenAI Swarm specifically).
- Abstract 0-10 risk score → no analogue found in any framework reviewed. `<certain>` under the same scope caveat as above.

**2. Does any framework gate fan-out on input magnitude, or all on runtime budget?**

All on runtime budget. The one place a framework's docs *mention* task/query complexity is Anthropic's blog: "Scale effort to query complexity... Simple fact-finding requires just 1 agent with 3-10 tool calls, direct comparisons might need 2-4 subagents with 10-15 calls each, and complex research might use more than 10 subagents" (https://www.anthropic.com/engineering/multi-agent-research-system). This is qualitative guidance embedded as instruction text in the lead agent's system prompt — the lead agent (an LLM) *judges* complexity and self-selects a budget; it is not a programmatic gate computed from a measurable input feature (e.g., byte count, token count of the query, file count). The blog explicitly says the opposite is a failure mode they fought: "Agents struggle to judge appropriate effort for different tasks." No numeric, code-enforced input-magnitude threshold exists in any source fetched. `<certain>`.

**3. Are documented defaults measured or asserted?**

Mixed, mostly asserted:
- Anthropic (measured, most rigorous of everything found): "three factors explained 95% of the performance variance in the BrowseComp evaluation... token usage by itself explains 80% of the variance, with the number of tool calls and the model choice as the two other explanatory factors." Also: "agents typically use about 4× more tokens than chat interactions, and multi-agent systems use about 15× more tokens than chats" — an explicit measured economic cost cited as the reason multi-agent fan-out needs task-appropriate gating. This is the only source in the review that ties a currency (tokens/tool-calls) to a controlled measurement and states the measurement. https://www.anthropic.com/engineering/multi-agent-research-system `<certain>`.
- Claude Code workflows' `16`/`1,000` caps: doc states the *reason* ("bounds local resource use," "prevents runaway loops") but not a measurement — asserted engineering judgment, not a benchmarked number. A live GitHub feature request (anthropics/claude-code#63938) confirms the cap is `min(16, cpu_cores - 2)`, i.e. derived from host resources, not from any workload measurement. https://code.claude.com/docs/en/workflows, https://github.com/anthropics/claude-code/issues/63938 `<certain>`.
- CrewAI `max_iter=20`: stated as a default with no rationale given in the docs page fetched. `<certain>` no justification is present in that doc — `<don't know>` whether one exists elsewhere (e.g. changelog, GitHub discussion; not searched this pass).
- LangGraph `recursion_limit=25`: stated as default; the third-party explainer speculates it maps to "Pregel super-steps" but no rationale for the number 25 specifically was found in LangChain's own docs. `<speculative>` on why 25 was chosen; `<certain>` that no primary-source justification was found in the docs fetched (https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT, https://forum.langchain.com/t/best-practices-for-parallel-nodes-fanouts/1900).
- AutoGen/AG2 `max_round`/`max_consecutive_auto_reply`: no numeric defaults documented at all in the FAQ; all examples in official docs and blog posts are user-set (6, 8, 12), with a third-party blog recommending "start at 6-8, increase only if needed" as a heuristic, not a framework default. `<certain>` no default-with-rationale found in AG2 docs fetched.

## Open questions (raised by sources, not recommendations)

- OpenAI Agents SDK ships no numeric `max_turns` default at all (`None` disables it) — unclear whether OpenAI considers an unbounded run acceptable by design or expects every caller to set one; not resolved in fetched docs.
- Claude Code's dynamic-workflow concurrency cap is explicitly requested to become user-configurable in an open GitHub issue (#63938) — the hard 16/cpu_cores-2 ceiling is contested by at least one power user as too conservative for research/verification workloads similar to fan-out review use cases.
- Not reviewed this pass: Google ADK, smolagents, Semantic Kernel, OpenAI Swarm (legacy) — absence of a distinct unit there is `<don't know>`, not `<certain>`.
- Anthropic's "token usage explains 80% of variance" finding is from one internal eval (BrowseComp-style browsing tasks) — generalization to a code-review/diff-fan-out domain is untested and not claimed by Anthropic.

## Confidence

Overall: `<certain>` for the primary claim (all reviewed frameworks gate on runtime budget, none on input magnitude) — every framework in the routed list was checked against a primary doc URL that resolved. Confidence is capped to `<don't know>` for the subset of frameworks not reviewed (Google ADK, smolagents, Semantic Kernel, Swarm), per the research question's "optionally" scope — they were not fetched this pass.

## Sources checked (all URLs extracted or search-confirmed this session)

- https://www.anthropic.com/engineering/multi-agent-research-system (primary, fetched via extract, advanced depth, twice)
- https://code.claude.com/docs/en/agent-sdk/subagents
- https://code.claude.com/docs/en/workflows
- https://code.claude.com/docs/en/agents
- https://github.com/anthropics/claude-code/issues/63938
- https://openai.github.io/openai-agents-python/running_agents
- https://openai.github.io/openai-agents-python/ref/run
- https://openai.github.io/openai-agents-python/release
- https://github.com/openai/openai-agents-python/issues/123
- https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/_internal/_config.py
- https://forum.langchain.com/t/best-practices-for-parallel-nodes-fanouts/1900
- https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT
- https://docs.langchain.com/oss/javascript/langgraph/use-graph-api
- https://docs.crewai.com/v1.15.5/en/concepts/agents
- https://docs.crewai.com/v1.15.5/en/learn/kickoff-async
- https://community.deeplearning.ai/t/automate-event-planning-the-crew-must-end-with-at-most-one-asynchronous-task/679677
- https://docs.ag2.ai/latest/docs/user-guide/FAQ
- https://docs.ag2.ai/latest/docs/user-guide/advanced-concepts/groupchat/groupchat
- https://docs.ag2.ai/latest/docs/use-cases/notebooks/notebooks/agentchat_groupchat_RAG

## Not available / not used

Context7 was not invoked this session — Tavily search + extract against primary vendor/GitHub docs covered every routed framework with resolvable URLs, so the fallback to Context7 was not needed. If a follow-up wants Context7-indexed snippet coverage (e.g., versioned LangGraph/CrewAI API references) that is an open gap, not a checked absence.
