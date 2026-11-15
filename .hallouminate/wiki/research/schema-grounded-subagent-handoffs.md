# Schema-grounded sub-agent handoffs: where the contract lives and when a worker pays off

A sub-agent should return a typed object, not prose. Only OMP gives that contract a first-class field. Claude Code, Codex, and Pi need a hook, a validator step, or an extension. Schemas belong on the sub-agent or tool definition, not in skill frontmatter. A worker pays off when its task is dirty but separable and returns a short summary.

Research ran on 2026-07-27 and 2026-07-28 as a Perplexity-style synthesis. Most sources are secondary: blog posts, videos, forum threads, and vendor docs. Confidence markers: `<certain>` means a vendor doc or an Anthropic post states it. `<speculative>` means a secondary source or this page infers it. `<don't know>` means the sources do not answer it.

## What this means for ADR-005

[ADR-005](../adr/deterministic-fanout-sizing-005.md) leaves "the size score and its inputs" and the degrade path to a follow-up `/mold`. Three findings bear on that work:

1. **Separability is an input to consider, not only size.** A large task that depends on accumulated design context fits a fresh-context worker poorly. A noisy, bounded task fits well even when small. Code can approximate separability from file overlap between pieces. This extends the "mixed pieces" question in ADR-005. `<speculative>`
2. **The one-worker outcome needs a return contract.** ADR-005 names "one fresh-context worker" as an outcome. The value of that worker is a short, decision-ready return. A size score that picks one worker should also pick a return shape. Easy-cheese already ships typed contracts in `src/easy_cheese_schemas/`, so the contract can be a published schema.
3. **The degrade path cannot assume native schema support.** Only one of four harnesses validates a sub-agent return natively. A degrade path that needs a typed return must validate in skill code or in a hook. See the table below. `<certain>` for the harness facts.

None of these findings supplies a threshold. No source measured a size at which a worker starts to pay off. `<don't know>`

## Harness support for typed returns

| Harness | Native mechanism | How to enforce a typed return |
| --- | --- | --- |
| Claude Code | No `output` field in sub-agent frontmatter | State the shape in the sub-agent body. Validate in a `PostToolUse` or `Stop` hook. |
| Codex CLI | Planner and worker pattern with JSON task schemas (`id`, `role`, `cwd`, `rules`, `deps`) | Run a validator step on the planner JSON before workers start. |
| Pi | No built-in sub-agents | Delegate through the `pi-subagents` extension, or call the Pi CLI with `--mode json`. Wrap it in a validating adapter. |
| OMP | First-class `output` frontmatter field, an opaque JSON schema, exclusive with prose output instructions | Use the native field. |

Sources: [Claude Code sub-agents](https://code.claude.com/docs/en/sub-agents), [Codex discussion on queue and worker sub-agents](https://github.com/openai/codex/discussions/3898), [pi-subagents](https://pi.dev/packages/pi-subagents), [OMP subagent authoring](https://omp.sh/docs/subagent-authoring). `<certain>` for OMP and Claude Code, which come from vendor docs. `<speculative>` for Codex and Pi: the Codex row describes a community pattern, not a Codex feature. The Pi facts come from a video walkthrough.

The wider claim is that a typed return removes the "re-parse prose" failure class. The Anthropic playbook PDF makes that claim as "the schema is the contract". The signed link in the source note is not reproduced here. `<speculative>` that the claim transfers from extraction pipelines to coding sub-agents. No source measures it.

## Where the schema lives

Claude Code skill frontmatter holds discovery and loading fields: `name`, `description`, `disable-model-invocation`, and `allowed-tools`. It has no input or output schema field ([skills docs](https://code.claude.com/docs/en/skills)). `<certain>` Frontmatter is also not where the harness validates a return.

- Put the schema in the skill body or a `references/` file, and enforce it at the sub-agent, tool, or validator layer.
- In OMP, the schema goes on the sub-agent file, not on a skill.
- In Pi, the schema goes in the extension's tool definition, not in skill markdown.

This agrees with the easy-cheese layout. Published schemas live in `src/easy_cheese_schemas/`, and skill prose names them. The skill Python bundle doctrine in `AGENTS.md` keeps schemas out of skill frontmatter by design.

## When a sub-agent helps coding

The secondary sources agree on one rule. Use a worker when the task is dirty and separable, and only a short summary must survive. Keep the work in the main thread when steps depend on design context a fresh window cannot rebuild.

| Good fit | Poor fit |
| --- | --- |
| Bounded exploration across many files | Iterative implementation on the same code |
| Parsing large test or log output | Later steps that depend on earlier in-session decisions |
| Review of a fixed diff, returned as a verdict | Several workers editing shared files at once |
| A scout task: find X, return a path and 20 lines | Work that needs the "why we chose this" context |

Evidence and limits:

- Anthropic says multi-agent research beats one agent by 90.2% and costs up to 15x the tokens. It also says most coding tasks have fewer parallel pieces than research. `<certain>` See [fan-out gating units](./fanout-gating-units-evidence.md) for the cost figures. The manifesto record sits in `docs/research/manifesto-2026-10/evidence-digests.md`.
- One practitioner report cuts a main thread from 169k tokens to 21k by moving log parsing to a sub-agent. The sub-agent used about 150k tokens off-thread and returned five lines. `<speculative>` This is a single anecdote from a video. Treat the numbers as an illustration of the airlock pattern, not as a measured effect.
- A framing from practitioner posts says sub-agents give context isolation, not parallelism. `<speculative>` It matches ADR-005's third outcome, which separates one fresh-context worker from parallel work.
- The "35-minute cliff" claim, where agent success drops in long sessions, comes from one video. `<don't know>` whether it holds. Do not use it as a design input.

## Handoff documents and shared stores

For long sessions, the sources prefer an explicit handoff document over auto-compaction. The document has a fixed shape: objective, decisions, open follow-ups, current state, and where to resume. `<speculative>` The wheypoint skill already does this with a typed record, so this research adds no new requirement there.

A shared store of typed entities (SQLite tables for entities, relations, aliases) helps only when facts must chain across workers that never read the same files. The source note calls it too heavy for most coding tasks. That agrees with the standing "no" in [fanout-artifact-format-question](../architecture/fanout-artifact-format-question.md).

_Source: Perplexity-style research synthesis, 2026-07-27 to 2026-07-28,
plus the vendor docs linked above · Promoted from the PR #358 research
scratch · Updated: 2026-11-15_
