## Introduction

The attached working note treats the knowledge graph as an infrastructure layer that solves a specific problem in multi-agent systems: each agent's context dies when its window closes, so any system that needs facts to survive across turns, workers, or sessions needs a durable, typed, provenance-carrying store underneath it. The core mechanism the paper leans on — Pydantic-schema structured outputs replacing free-form text as the contract between pipeline stages — generalizes directly to how sub-agents should hand off work in Claude Code, Codex, Pi, and OMP. This report addresses four questions: how to apply graph/schema thinking to sub-agent handoffs, whether skill frontmatter is the right place for input/output schemas, when sub-agents help versus hurt for coding, and how to design a long-handoff, efficient one-shot session.[^1]

## Schema-Grounded Handoffs Across Harnesses

The paper's central architectural claim is that "the schema is the contract": an API call either returns a valid typed object or raises an error, eliminating the parsing/validation failure class entirely. This is exactly the failure mode that plagues sub-agent handoffs in coding harnesses — a sub-agent returns a paragraph of prose, and the parent has to re-parse intent, file paths, and next steps out of natural language, which is a lossy, error-prone step. Applying the paper's discipline means every sub-agent should return a structured object, not a narrative, and the object's shape should be versioned the same way the paper insists on versioning the extraction schema — "a production pipeline versions the schema alongside the graph, so that entities extracted under different prompts can be distinguished, compared, and re-extracted".[^1]

Each harness supports this pattern differently:

| Harness | Native schema mechanism | How to enforce typed handoffs |
|---|---|---|
| Claude Code | `output` is not a native subagent frontmatter field, but subagents can be instructed to emit JSON matching a documented shape; tool calls and hooks can validate | Define the return contract in the subagent's markdown body as a strict JSON block; use a `PostToolUse`/`Stop` hook to validate against a JSON Schema and reject malformed returns[^2][^3] |
| Codex CLI | Planner/worker pattern with explicit JSON task schemas (`id`, `role`, `cwd`, `rules`, `deps`) validated before dispatch[^4] | Use a "Validator" step exactly as the community pattern does — parse and normalize the planner's JSON against a schema before workers execute[^4] |
| Pi | No built-in sub-agents by default; delegation happens via an extension (`pi-subagents`) or by another harness calling the Pi CLI and parsing its JSON event stream[^5][^6] | Because Pi exposes `--mode json` structured event streaming, wrap the CLI call in a schema-validating adapter in the calling harness rather than relying on prose parsing[^5] |
| OMP | First-class: `output` frontmatter field takes an "opaque JSON schema for structured returns," explicitly documented as mutually exclusive with prose output instructions[^7] | Use the native `output` field — this is the closest analogue to the paper's `output_format=ExtractedGraph` pattern[^1][^7] |

OMP is the only harness among the four with a first-class, documented schema field for sub-agent returns, making it the most direct implementation of the paper's `client.messages.parse(output_format=...)` pattern. For Claude Code, Codex, and Pi, the same discipline has to be layered on manually: define a Pydantic or JSON-Schema contract, put it in the sub-agent's instructions verbatim (the way the paper's extraction prompt embeds the `ExtractedGraph` shape as text), and validate the returned JSON before the parent trusts it.[^7][^1]

### Applying the Knowledge-Graph Pattern Specifically

Where this becomes genuinely useful — not just typed JSON for its own sake — is when multiple sub-agents need to accumulate a shared, queryable world model rather than pass isolated blobs back to one orchestrator. The paper's Table II maps this precisely: orchestrator-workers uses the graph as shared memory so "the orchestrator's context stays small; the shared state lives in the graph, queryable by any agent at any time". Translated to a coding harness, this means:[^1]

- Define entity types for your domain (e.g., `Endpoint`, `Migration`, `Config`, `TestFailure`) the same way the paper defines `PERSON`/`ORGANIZATION`/`LOCATION`.[^1]
- Have each sub-agent (a "scout" that greps the codebase, a "reviewer," an "implementer") emit typed entities/relations as its return value instead of prose, using the extraction schema pattern (`name`, `type`, `description` for disambiguation).[^1]
- Persist these into a lightweight store (SQLite/Postgres tables mirroring the paper's `entities`, `relations`, `aliases` schema is sufficient at repo scale — NetworkX/Neo4j is overkill for most codebases).[^1]
- Let a synthesizer or the main session query that store for multi-hop questions ("which services call the endpoint I'm about to deprecate") instead of re-reading five sub-agent transcripts.

This is a heavier lift than most coding tasks warrant, but it is the right pattern specifically for cross-cutting refactors, dependency-graph questions, or incident/root-cause work where facts must be chained across files that no single sub-agent read together — the same "no single worker saw all three facts" problem the paper's competitive-intelligence example describes.[^1]

## Should Input/Output Schemas Live in Skill Frontmatter?

Claude Code's skill frontmatter is documented as a small, intentionally limited set of fields: `name`, `description`, `disable-model-invocation`, and `allowed-tools`. There is no native `input`/`output` schema field for skills — schemas belong to structured-output API calls (as in the paper) or to sub-agent/tool definitions, not to skill metadata. Putting a full JSON Schema inline in skill frontmatter is workable syntactically (YAML can hold arbitrary nested data) but goes against the documented design intent: frontmatter fields are meant to control *when and how* a skill loads, not to define the *data contract* of its output.[^8][^9]

The better placement, consistent across all four harnesses:

- **Claude Code**: put the input/output schema in the skill's markdown body (or a `references/schema.md` file it points to), and enforce it at the sub-agent or tool-definition layer — sub-agent frontmatter supports `output`-adjacent behavior only indirectly (via prose instructions), so validation should happen through a hook rather than frontmatter.[^3][^8]
- **OMP**: this is the one place a schema genuinely belongs in frontmatter, because OMP's `output` field on the *sub-agent* definition is explicitly built for this ("opaque JSON schema for structured returns. Conflicts with prose output instructions; pick one"). Skills and sub-agents are separate concepts in OMP; the schema goes on the sub-agent file, not a skill file.[^7]
- **Codex/Pi**: neither has a skill-frontmatter concept identical to Claude Code's; Codex's pattern puts the schema in the planner's system prompt as a JSON template the planner must follow, validated by a separate step. Pi treats capability extension as skills (markdown, read on demand) or extensions (real TypeScript tool functions) — a schema belongs in the extension's tool definition, not the skill markdown, mirroring Claude Code.[^4][^5]

The general rule that falls out of the paper's own architecture: skills/reference docs are "content that runs inline" and shapes reasoning, while schemas are enforcement contracts that belong wherever the harness validates a return value — the sub-agent definition, the tool definition, or an explicit validator step, not the discovery metadata that decides whether to load a skill at all.[^8][^1]

## When to Use Sub-Agents for Coding — and When Not To

The paper itself flags the tension directly: multi-agent systems outperform single agents by 90.2% on tasks requiring multiple independent directions, but consume 10-15x more tokens and require careful context management. Independent reporting on Claude Code sub-agents sharpens this into a coding-specific verdict: sub-agents show large gains for research-style tasks but perform worse than main-thread usage for coding, because each sub-agent starts with zero knowledge of prior decisions, existing patterns, or trade-offs, and Anthropic's own guidance states "most coding tasks involve fewer truly parallelizable tasks than research, and LLM agents are not yet great at coordinating and delegating to other agents in real time".[^10][^1]

The mechanism behind this is context isolation, not capability. Sub-agents get a fresh context window and cannot see the parent's history, peer sub-agents' state, or the reasoning that produced current code — so parallel sub-agents editing related code frequently make conflicting assumptions and the user ends up spending more time on integration than sequential coding would have taken. A widely cited practitioner framing calls sub-agents "context isolation, not parallelism": their real value is using tokens *outside* the main window for messy exploration, with the return contract mattering more than the initial prompt.[^11][^12][^10]

| Good fit for sub-agents | Poor fit for sub-agents |
|---|---|
| Noisy, bounded exploration: grepping/reading many files, parsing huge test/log output[^13][^14] | Iterative back-and-forth implementation on the same code[^15][^16] |
| Independent, parallelizable research directions (multiple analysts, no shared state needed)[^1][^10] | Multi-phase work where later steps depend on earlier design decisions made in-session[^15] |
| Code review / QA against a fixed diff, returned as a distilled verdict[^10] | Race conditions on shared files edited by multiple sub-agents concurrently[^15] |
| One-shot "scout" or "librarian" tasks: find X, return a path and 20 relevant lines[^14] | Tasks requiring continuous access to "why we made this choice" context that isn't re-suppliable in a short task description[^11] |

The decision rule that emerges across sources: use a sub-agent when the task is dirty/token-heavy but *cleanly separable*, and the only thing that needs to survive is a short, decision-ready summary; keep work in the main thread when steps are interdependent and require accumulated design context that a fresh window cannot reconstruct without re-supplying most of what isolation was meant to avoid. Practically: a "run tests, parse 150k tokens of logs, return root cause + suggested fix" sub-agent is close to free — it returns 5,000 tokens instead of dumping 150,000 into the main thread, an 8x reduction in one reported case. A sub-agent asked to "implement the feature" instead is fighting the isolation the pattern is built on.[^13][^14][^12]

## Building an Efficient Long-Handoff, One-Shot Session

"One-shot" here means completing a long, complex piece of work without the interactive back-and-forth a chat session implies — feeding a single rich prompt (or resumed session) and letting the harness run to completion, then handing off cleanly to either a human or the next session. Three complementary techniques, all consistent with the paper's "session is not the context window" principle borrowed from Anthropic's Managed Agents architecture, make this tractable:[^1]

**1. Treat the session like the paper treats the graph: durable, append-only, and interrogable by slice.** The paper's persistent-world-model role is explicit — "the session — here, the knowledge graph — is durable, append-only, and interrogable by positional slice. It does not vanish when a worker's context is flushed". Pi implements this literally: sessions are stored as a tree, forkable at any point via `/tree`, and any branch can be summarized with a custom prompt before resuming — so a long one-shot run can be checkpointed and continued without re-explaining state. Claude Code's equivalent is auto-compaction plus manually maintained state files (CLAUDE.md, or a dedicated handoff skill) that survive `/clear`.[^17][^5][^18][^1]

**2. Push noisy, token-intensive work into isolated sub-agents and keep only the summary in the main thread — the "context airlock" pattern.** One documented case reduced a main thread from 169,000 tokens (91% diagnostic noise) to 21,000 tokens (76% signal) by moving test-log parsing into a sub-agent that burned 150,000 tokens off-thread and returned a five-line root-cause report. This is the direct coding analogue of the paper's summarization stage, which pools many raw mentions into one dense profile so downstream consumers never see the raw material. For a genuinely long one-shot session, this is what keeps the *main* context from hitting the "35-minute cliff" where attention dilution and lost-in-the-middle effects degrade output quality regardless of window size.[^15][^13][^1]

**3. Use explicit handoff artifacts instead of relying on compaction summaries.** Auto-compaction blurs decisions and follow-ups because it is a generic summarizer, not a structured handoff. The more reliable approach — used by dedicated "next-session-prompt" style skills — captures a single markdown resume document with a fixed schema: objective, decisions made, outstanding follow-ups, current state, and where to resume, then pastes that into a fresh session to continue with full effective context at a fraction of the token cost. This mirrors the paper's advice on evaluator-optimizer loops: feedback should include "not just 'this is wrong' but the specific graph evidence that contradicts it" — a good handoff is not "I did some stuff," it is a structured, checkable record of state.[^19][^1]

Practically, for Paul's stack (Claude Code, Codex, Pi, OMP): design the handoff object once as a shared schema — objective, files touched, tests run/passing, open decisions, next action — and use whichever harness-native mechanism stores it durably (Pi's `/tree` summarize-with-prompt, a Claude Code CLAUDE.md-resident state block plus a `/compact`-triggering hook, or a Codex-style validator-checked JSON plan file). The schema itself is the reusable artifact across harnesses; only its storage mechanism changes.[^18][^4][^17]

## Synthesis

The paper's headline insight — that structured, typed contracts eliminate an entire class of pipeline failure that free-form text handoffs are prone to — is directly portable to sub-agent design, but only OMP currently gives that contract a first-class home in sub-agent frontmatter; Claude Code, Codex, and Pi require bolting the same discipline on via hooks, validator steps, or extension tool definitions. Skill frontmatter, across every harness, is metadata for *discovery and loading*, not for *data contracts* — schemas belong on the sub-agent or tool definition, one layer down. And the sub-agent-for-coding question resolves to a single test: is the task dirty-but-separable, returning a short decision-ready summary (good fit), or does it require the accumulated design context a fresh window cannot reconstruct (poor fit, stay in the main thread). Long one-shot sessions are best engineered as a combination of isolated sub-agents doing the noisy work and an explicit, schema-shaped handoff document rather than relying on generic auto-compaction to preserve state.[^2][^5][^4][^10][^13][^19][^11][^8][^7][^1]

---

## References

1. [Graph-Engineering-Athropic-Playbook.pdf](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/57186735/f6d29768-1625-4017-940a-4f5e0fe39233/Graph-Engineering-Athropic-Playbook.pdf?AWSAccessKeyId=ASIA2F3EMEYESCZ2QKCS&Signature=m%2F%2BhyiT27iPWFPnQ%2BUyyQVN8Vwk%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEJf%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJHMEUCIQC4KgCnbvXrHLW5GypbVRv37RnV4Npnz1B7LOn8wpve3gIgdzvoXbavcXUL2Zw%2BFxin3k3gajKsh1VOOscVkO12Wbgq8wQIYBABGgw2OTk3NTMzMDk3MDUiDBUEY1IQ9LafliFpoirQBN%2BE8eKH%2FuzLmLMR00Kk4SizQ7JxpIILB4muJ1cEP8rFrxV1GRonKEKhLg9h4SUjggstt6TlH87X3A0zDhfiwkpQNbjw3%2B9Sx2qT2MfokSsM3aFnJobtyTYeGDNdWx42ev5trBjPeUNkTSBt3AwfUWWEnWUm7MTUGZjjhKWK8diCIK5aha8Lvl363zAeE8Ba0TphfFwBgeHeJ0aCKl1vsxFapL6g7HY2yEvD3j%2F3A0q1g0sV1abPD6fUTMUS4lplus%2FZbX%2BQrLt%2BVBDNbapnNQaUvht2hDkUlU45virpf2Mw6TqemSQnI7AqCpBN%2FuhYpl8r2LJn9%2BexCRmFBQhgNuzuQHLmPJZHgvlHhn5zgm7k8grKQJYuLFIZCvZsWzbWE0WZo7nwuLCEeOPDRqBPLvmU9oTMCsAP2j88ygUnOCpki9nHVBqJbWOjSEO05pDuILp3dLOYOufYD9B87tLDQGno2iqF483hifMjbeo0CpJSNSGXKg6Ic6DFMjPH3cijLbSyJw%2B2ETsbKUMMeqch5N5OLhoRnBejfoFWd%2BEzvpSXYtgGY7T2L3QaY8cGzXTlJMh3c2iblHTZ8tL%2FLsL6tjX5WX47TRjHyzkmq5886cL8ikCa0i%2FWceou4pln5aSn1WqCpQW3a33aVmjhaNQClJtvgbls35k53LBd1wA%2BSwD0JTgkTzTzqvP%2FHnKiO%2Fn4IHJwaJbYNMDbW%2By5LsP1uf0xi8Ef%2BHx0OgWROwzwmBP26qlkhO8gtz5W9rtCqSXdeTerilzUSHxVQxXsFr0v%2FF0w8KKh0wY6mAHECWJIVoAZRW4W8sd15TMrfVYEekMoK2zJpvUGmeD9So10Uwz0CRI6vd36A%2Bq7YCrukiqRR5Xpnx9J7cavH%2BLHej7Gh9%2FCSxuvXnHMeI0bv%2FZvnZH%2FJ8Ga35n6%2Fk2oSqGRxI7L8ubhKsNz%2BeqUZLwBUqVVKrWiP%2FUBEsK4kzHzpmsp1zo27X6dE3NFB97cjU%2B7fcyY6w475g%3D%3D&Expires=1785225027)

2. [Create custom subagents - Claude Code Docs](https://code.claude.com/docs/en/sub-agents)

3. [claude-code-best-practice/best-practice/claude-subagents.md at main](https://github.com/shanraisshan/claude-code-best-practice/blob/main/best-practice/claude-subagents.md) - from vibe coding to agentic engineering - practice makes claude perfect - shanraisshan/claude-code-b...

4. [How to orchestrate “sub-agents” with Codex CLI (queue/worker ...](https://github.com/openai/codex/discussions/3898) - 1. Goal I’d like to run multiple sub-agents with Codex CLI that collaborate via a queue (producer/co...

5. [Pi Agent Harness, Clearly Explained | No MCP, No Sub ...](https://www.youtube.com/watch?v=0sI0MbCt4f4) - Pi, the coding agent harness by Mario Zechner … no sub agents, no plan mode, no to-dos, and no permi...

6. [pi-subagents · Packages](https://pi.dev/packages/pi-subagents) - pi-subagents lets Pi delegate work to focused child agents. Use it for code review, scouting, implem...

7. [Authoring subagents - a coding agent with the IDE wired in](https://omp.sh/docs/subagent-authoring) - Subagents, plan mode, LSP, DAP, hindsight memory, hashline edits, time-traveling rules — with a nati...

8. [Extend Claude with skills - Claude Code Docs](https://code.claude.com/docs/en/skills) - Create, manage, and share skills to extend Claude's capabilities in Claude Code. Includes custom com...

9. [SKILL.md - anthropics/claude-code - GitHub](https://github.com/anthropics/claude-code/blob/main/plugins/plugin-dev/skills/skill-development/SKILL.md?plain=1) - Claude Code is an agentic coding tool that lives in your terminal, understands your codebase, and he...

10. [Claude Code Sub-Agents: When NOT to Use Them](https://www.linkedin.com/pulse/understanding-claude-code-sub-agents-when-use-them-michael-hofer-rz9le) - Sub-agents are great for research tasks but terrible for coding due to context isolation. They consu...

11. [Subagent Context Isolation - Albert Masoliver's learning site](https://albertml.com/Permanent/AI/AI+Agents+and+Patterns/Subagent+Context+Isolation) - Definition Subagent context isolation is the architectural property that each subagent in the Orches...

12. [Sub-agents are context isolation, not parallelism, or what I ...](https://www.reddit.com/r/ClaudeAI/comments/1v744d1/subagents_are_context_isolation_not_parallelism/) - Sub-agents are context isolation, Isolation means the sub-agent knows only what you explicitly hand ...

13. [Slash Commands vs Subagents: How to Keep AI Tools ...](https://jxnl.co/writing/2025/08/29/context-engineering-slash-commands-subagents/) - The key insight is that subagents should operate in isolation on well-defined tasks, then return dis...

14. [Stop Treating Subagents Like Role-Players: The Case for ...](https://sabarnathm.medium.com/stop-treating-subagents-like-role-players-the-case-for-context-isolation-1b448b21bd91) - By Sabarnath Maddinieni

15. [4 - The Real Fix for Context Rot: Subagent Isolation Explained](https://www.youtube.com/watch?v=7XkTpLQtuuo) - From Playlist 3 episode 4: by 35 minutes into a long agent session, every AI agent's success rate dr...

16. [Hacker News](https://news.ycombinator.com/item?id=45231217)

17. [Claude Code Context Management: /clear, /compact, and Session ...](https://blink.new/blog/claude-code-context-management) - How to manage context in Claude Code sessions — when to use /clear vs /compact, CLAUDE.md as memory,...

18. [Pi replaced every other coding agent harness for me](https://www.youtube.com/watch?v=jPuN4ilZLdU) - Pi is a minimal coding agent harness, it ships with almost nothing out of the box, which means you s...

19. [Save and Resume Any Claude Code Session | Next Session Prompt Skill](https://www.youtube.com/watch?v=V0BkDqHZUcA) - Save and resume any Claude Code session before you hit the context window limit, using a free skill ...

