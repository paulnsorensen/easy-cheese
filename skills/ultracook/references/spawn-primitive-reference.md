# Spawn-primitive reference

`/ultracook` parallel mode spawns sub-agents via the host harness's fan-out primitive; both modes spawn each phase as a fresh-context sub-agent. The orchestrator is harness-agnostic — any primitive that satisfies all five invariants below is acceptable. This file collects host-by-host invocation examples plus the five invariants.

## The five invariants

A spawn primitive is acceptable iff it satisfies all five:

1. **Fresh context per spawn.** The sub-agent boots with no memory of prior phases. The orchestrator's chain-of-thought, prior tool outputs, and conversation history are all dropped at spawn boundary.
2. **Full-peer capability — gated on capability, not on the type label (issue #197).** The spawn must inherit the parent's model, full tool access, full skill access, and full MCP access. A specialized `subagent_type` (e.g. a typed coder/reviewer) is acceptable *when it clears that capability bar*; the gate is capability, never the `subagent_type` string. Reject only diminutive workers — a downgraded model (haiku) or a scoped read-only type that lacks the tools a phase needs. This capability gate governs both /ultracook modes and /ultracook-fleet.
3. **No chain-forward.** The sub-agent runs only its phase and returns. The no-chain-forward directive must be passed in the prompt — the host primitive does not enforce it.
4. **Returns control.** The orchestrator regains control after each spawn so it can read the handoff slug. Fire-and-forget primitives do not satisfy this invariant.
5. **Writes handoff slug.** Each spawn writes its result to `.cheese/<phase>/<slug>.md` per the schema. The orchestrator decides chain progression from the slug, never from stdout.

If the host harness exposes no spawn primitive that satisfies all five invariants, halt `/ultracook` and recommend `/cook --auto`. Running in the parent's context explicitly drops `/ultracook`'s fresh-context guarantee.

## Anthropic Claude Code — `Agent()` / `/batch`

[`/batch`](https://code.claude.com/docs/en/commands) dispatches multiple `Agent()` calls in a single message — that's the fan-out primitive `/ultracook` parallel mode uses for the per-curd wave.

```text
Agent(
  subagent_type: "general-purpose",   # or a typed full-peer (e.g. coder) — gate on capability, not the label
  # model: omit — inherits parent's model. Do not pass haiku/sonnet here.
  prompt: "Run /<phase> <slug> --auto for THIS PHASE ONLY. Write
           .cheese/<phase>/<slug>.md with the handoff schema and stop.
           Do not chain forward to the next phase even though your
           auto-mode contract documents that. The /ultracook orchestrator
           is driving the chain.
           Run in the foreground — do not background yourself, spawn
           detached processes, or defer work to a later session.
           If you cannot complete the phase within your context window,
           write a partial slug with status: halt: <reason> and stop; do not
           silently timeout."
)
```

Rules:

- **Do not downgrade the model.** Omit the `model` parameter so the sub-agent inherits.
- **Gate `subagent_type` by capability, not by label (issue #197).** `general-purpose` always qualifies; a specialized type (e.g. a typed `coder`/`reviewer`) is equally fine *when it is a full peer* — parent's model, full tools, full skills, full MCP. Reject only diminutive types: read-only / scoped workers (`Explore`, `lsp-probe`) that lack the tools a phase needs, or a downgraded model.
- **Do not restrict tools or MCP access.** Each phase needs Bash, Edit, Write, Read, the `cheez-*` skills, and any MCP servers the parent has.
- **Do pass the slug.** The phase skill resolves its own paths from the slug.

## GitHub Copilot CLI — fleets

[Copilot CLI fleets](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/fleet) dispatch multiple agents from a single CLI invocation. Each agent boots in its own conversation context, satisfying invariant 1.

```sh
copilot fleet \
  --agents 5 \
  --prompt-file .cheese/ultracook/<slug>/curd-prompts.txt \
  --return-on-completion
```

Rules:

- Each prompt in the prompt file must include the no-chain-forward directive and the foreground-only directive (run in the foreground; do not background yourself or defer work; write a partial slug with `status: halt: <reason>` if the context window is exhausted, do not silently timeout).
- `--return-on-completion` is mandatory; without it, control does not return to the orchestrator (invariant 4 fails).
- Fleet agents inherit the same model and tool scope as the parent session, satisfying invariant 2.
- Each agent must write the handoff slug to `.cheese/ultracook/<slug>/curds/<id>.md` per the per-curd prompt template.

## OpenAI Codex: host-exposed sub-agent capability

In Codex sessions, use the host's exposed spawn capability rather than assuming a versioned tool name. For example, a host may expose `collaboration.spawn_agent`:

```text
collaboration.spawn_agent(
  task_name: "<phase>-<slug>",
  fork_turns: "none",
  message: "Run /<phase> <slug> --auto for THIS PHASE ONLY. Write
           .cheese/<phase>/<slug>.md with the handoff schema and stop.
           Do not chain forward to the next phase even though your
           auto-mode contract documents that. Run in the foreground..."
)
```

Rules:

- Omit model overrides unless the user explicitly requests one; the spawn should inherit the parent model where the host supports it.
- Request the host's no-context mode (`fork_turns: "none"` in this example); inheriting conversation turns violates invariant 1.
- Choose a full-peer, write-capable worker that satisfies invariant 2. Reject scoped read-only workers that lack a phase's tools.
- Wait for the returned agent before reading the handoff slug; fire-and-forget dispatch fails invariant 4.
- The prompt must include the no-chain-forward directive and the foreground-only directive (run in the foreground; do not background yourself or defer work; write a partial slug with `status: halt: <reason>` if the context window is exhausted, do not silently timeout).

## Other / future harnesses

Any primitive that satisfies the five invariants is acceptable. When evaluating a new harness:

1. Boot a sub-agent and verify it has no memory of prior phases (invariant 1). A simple check: ask the sub-agent to name the prior phase. If it can, the primitive is not fresh-context.
2. Confirm the sub-agent has the same tool / MCP access as the parent (invariant 2).
3. Confirm the prompt-level no-chain directive is honoured (invariant 3).
4. Confirm control returns synchronously (invariant 4).
5. Confirm the sub-agent can write files inside `.cheese/` (invariant 5).

If any invariant fails, halt `/ultracook` and recommend `/cook --auto`, explicitly noting that it runs in the parent's context and does not provide `/ultracook`'s fresh-context guarantee.
