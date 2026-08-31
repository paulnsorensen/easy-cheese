# Agent resolution

Resolve agent capabilities before dispatch. Agent names are hints; the runnable contract is the requested work, tools, permissions, isolation, minimum power, effort, and topology.

## Resolution order

Apply these gates in order for every requested agent:

1. **Capability floor.** Reject candidates missing a required tool, write capability, permission boundary, or isolation property. Missing required tools or required write capability halts the dispatch; do not pretend prompting supplies them.
2. **Minimum power.** Power is `cheap | default | powerful`; effort is `low | medium | high`. Reject a candidate known to be below the requested power. A candidate whose power is unknown is eligible only as the final fallback and sets `degraded: true`.
3. **Specificity.** Among eligible candidates choose an exact easy-cheese specialist, then a compatible specialist, then a general worker.

A general worker may fill a read-only role when the host cannot restrict tools: make the no-write constraint explicit in the prompt, record `permission_enforcement: prompt-only`, and set `degraded: true`. Prompt-only enforcement never qualifies a worker for a role that requires write capability or stronger isolation than the host provides.

## Required artifact block

Every canonical artifact written by a run that resolves or dispatches agents carries the same `agent_resolution` block. Preserve rejected attempts: resolution provenance is part of reproducibility, not debug trivia.

```yaml
agent_resolution:
  request:
    work: <bounded task>
    preferred_types: [<exact easy-cheese type>, <compatible type>]
    required_tools: [<tool-or-capability>]
    permissions: read-only | write
    isolation: none | fresh-context | isolated-worktree
    minimum_power: cheap | default | powerful
    effort: low | medium | high
  attempts:
    - type: <candidate type>
      model: <model id | unknown>
      power: cheap | default | powerful | unknown
      result: accepted | rejected
      reason: <why>
  resolved:
    type: <selected type>
    model: <model id | unknown>
    power: cheap | default | powerful | unknown
    effort: low | medium | high
    topology: inline | sequential | parallel | fan-out-fan-in
  fallback_reason: <null or why a lower-specificity candidate won>
  degraded: false
  permission_enforcement: tool-restricted | prompt-only
```

`request.required_tools` and `request.preferred_types` are nonempty. `attempts` is ordered and contains exactly one accepted entry; its type, model, and power match `resolved`. Power ranks `cheap < default < powerful`: known underpowered candidates are rejected, while unknown power may be accepted only as the final attempt and sets `degraded: true`. `fallback_reason` is null when the first preferred type is accepted and a nonempty reason for every lower-specificity selection. `permission_enforcement: prompt-only` requires both `degraded: true` and a read-only request. All artifacts for one dispatch share the same resolution facts; do not rewrite the story differently in a phase report and its handoff.

## Halt conditions

- Halt when no candidate has every required tool.
- Halt when write work has no write-capable candidate.
- Halt when required worktree or fresh-context isolation is unavailable.
- Do not turn a known underpowered candidate into a fallback.
- Use unknown power only after every known-power candidate is rejected, and record the degradation.

## Roles x tiers (spawn-primitive power and effort per role)

Each role's spawn-primitive `minimum_power` and `effort` defaults, harness-agnostic (harness-specific model/tier bindings live in `routing-policy.md`'s Roles x tiers table):

| Role | Minimum power | Effort | Notes |
|---|---|---|---|
| explorer | default | low | judgment-shaped digests stay at a capable-but-cheap tier; schema-constrained scans may go cheaper |
| researcher | default | medium | unchanged |
| coder | default | medium | gains the ESCALATE contract; delegation IS the downgrade |
| verifier | cheap | low | "verify exactly one claim"; schema-constrained; the cheap severity-filter leg |
| reviewer | powerful | low \| medium \| high (dial) | pinned to a powerful model; count and effort follow the age router |
| planner / integrator | powerful | xhigh (at mold) | never delegated; owns the approval loop |

A local skill table's `Effort` column defaults to this table for the matching role; override only with a stated reason (e.g. a router-driven dial).

## Phases x roles (per-phase model selection)

Model and effort are selected **per phase**, from the phase's role — not inherited from whatever model the dispatching orchestrator happens to be running. A phase spawn that omits the model is underspecified, not "the parent's model by default".

| Phase | Role | Minimum power | Effort |
|---|---|---|---|
| mold | planner / integrator | powerful | xhigh |
| cook | coder | default | medium |
| press | coder | default | medium |
| age (first and final) | reviewer | powerful | dial: low \| medium \| high, set by the age router |
| cure | coder | default | medium |
| wiring task | coder | default | low — single-file glue, capped at ~20 tool calls |

Resolve each phase against this table, run the resolution order above over the result, and record the resolved `model`, `power`, and `effort` in that phase's own `agent_resolution` block. A phase that resolves to a different model than the phase before it is normal; a phase whose `resolved.model` is `unknown` because nobody chose one is a degraded dispatch and carries `degraded: true`.

## Local skill tables

Each dispatching skill declares a local `## Agent resolution` table with the columns `Work`, `Preferred types`, `Permissions/isolation`, `Minimum power`, `Effort`, and `Fallback`. The table narrows this shared algorithm; it does not replace it.
