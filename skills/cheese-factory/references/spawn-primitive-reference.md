# Spawn-primitive reference

`/cheese-factory` spawns sub-agents via the host harness's fan-out primitive. The orchestrator is harness-agnostic — any primitive that satisfies all five invariants below is acceptable. This file collects host-by-host invocation examples plus the five invariants.

## The five invariants

A spawn primitive is acceptable iff it satisfies all five:

1. **Fresh context per spawn.** The sub-agent boots with no memory of prior phases. The orchestrator's chain-of-thought, prior tool outputs, and conversation history are all dropped at spawn boundary.
2. **Full-peer inheritance.** Same model as the parent, full tool access, full skill access, full MCP access. No diminutive workers (haiku, scoped read-only types).
3. **No chain-forward.** The sub-agent runs only its phase and returns. The no-chain-forward directive must be passed in the prompt — the host primitive does not enforce it.
4. **Returns control.** The orchestrator regains control after each spawn so it can read the handoff slug. Fire-and-forget primitives do not satisfy this invariant.
5. **Writes handoff slug.** Each spawn writes its result to `.cheese/<phase>/<slug>.md` per the schema. The orchestrator decides chain progression from the slug, never from stdout.

If the host harness exposes no fan-out primitive at all, `/cheese-factory` is the wrong skill — recommend `/ultracook` for the same review semantics in the parent's own context.

## Anthropic Claude Code — `Agent()` / `/batch`

[`/batch`](https://code.claude.com/docs/en/commands) dispatches multiple `Agent()` calls in a single message — that's the fan-out primitive `/cheese-factory` uses for Phase 2.

```text
Agent(
  subagent_type: "general-purpose",   # never specialised
  # model: omit — inherits parent's model. Do not pass haiku/sonnet here.
  prompt: "Run /<phase> <slug> --auto for THIS PHASE ONLY. Write
           .cheese/<phase>/<slug>.md with the handoff schema and stop.
           Do not chain forward to the next phase even though your
           auto-mode contract documents that. The /cheese-factory orchestrator
           is driving the chain.
           Run in the foreground — do not background yourself, spawn
           detached processes, or defer work to a later session.
           If you cannot complete the phase within your context window,
           write a partial slug with status: halt and stop; do not
           silently timeout."
)
```

Rules:

- **Do not downgrade the model.** Omit the `model` parameter so the sub-agent inherits.
- **Do not narrow `subagent_type`.** Use `general-purpose` (or the harness equivalent that grants full tool access). Do not pass `Explore`, `lsp-probe`, or any other read-only / scoped worker type.
- **Do not restrict tools or MCP access.** Each phase needs Bash, Edit, Write, Read, the `cheez-*` skills, and any MCP servers the parent has.
- **Do pass the slug.** The phase skill resolves its own paths from the slug.

## GitHub Copilot CLI — fleets

[Copilot CLI fleets](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/fleet) dispatch multiple agents from a single CLI invocation. Each agent boots in its own conversation context, satisfying invariant 1.

```sh
copilot fleet \
  --agents 5 \
  --prompt-file .cheese/cheese-factory/<slug>/curd-prompts.txt \
  --return-on-completion
```

Rules:

- Each prompt in the prompt file must include the no-chain-forward directive and the foreground-only directive (run in the foreground; do not background yourself or defer work; write a partial slug with status: halt if the context window is exhausted, do not silently timeout).
- Fleet agents inherit the same model and tool scope as the parent session, satisfying invariant 2.
- Each agent must write the handoff slug to `.cheese/cheese-factory/<slug>/curds/<id>.md` per the per-curd prompt template.

## OpenAI Codex — subagents

[Codex subagents](https://developers.openai.com/codex/subagents) are spawned via the `codex subagent` command or the `subagent` tool.

```sh
codex subagent \
  --type general-purpose \
  --prompt-file .cheese/cheese-factory/<slug>/curd-<id>.txt \
  --inherit-tools \
  --wait
```

Rules:

- `--type general-purpose` (or equivalent) — never pass a scoped worker type.
- `--inherit-tools` — full-peer inheritance per invariant 2.
- `--wait` — synchronous return so the orchestrator can read the handoff slug.
- The prompt file must include the no-chain-forward directive and the foreground-only directive (run in the foreground; do not background yourself or defer work; write a partial slug with status: halt if the context window is exhausted, do not silently timeout).

## Other / future harnesses

Any primitive that satisfies the five invariants is acceptable. When evaluating a new harness:

1. Boot a sub-agent and verify it has no memory of prior phases (invariant 1). A simple check: ask the sub-agent to name the prior phase. If it can, the primitive is not fresh-context.
2. Confirm the sub-agent has the same tool / MCP access as the parent (invariant 2).
3. Confirm the prompt-level no-chain directive is honoured (invariant 3).
4. Confirm control returns synchronously (invariant 4).
5. Confirm the sub-agent can write files inside `.cheese/` (invariant 5).

If any invariant fails, document the limitation in the host capabilities section of the manifest and route to `/ultracook` (sequential, same context) instead.
