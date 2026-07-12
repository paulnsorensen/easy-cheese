# Harness Portability

Use this reference when a skill needs to talk about host capabilities instead of one harness's syntax. Helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions are capability contracts. The portable docs name the contract first and only then show a host example.

## Helper resolution

Prefer repo-local or bundled helpers first:

- `shared/scripts/*.py` for repo-wide helpers such as corpus path resolution, handoff artifact writing, and slug readers.
- `skills/<skill>/scripts/*.pyz` for skill-specific helpers bundled with the repo.
- `${CLAUDE_SKILL_DIR}/scripts/*` only when the host actually provides that environment variable.

If a helper path is shown, the doc should say what behavior the helper provides, not imply one absolute path is the only valid transport.

## Read, search, edit, inspect

Use the host primitive that preserves bounded context. When the host offers multiple primitives, prefer the one that returns fresh line or snapshot context and call out the fallback only as a fallback.

## User interaction

Build the semantic question or handoff record first, following the shared [`handoff-gate.md`](handoff-gate.md) contract. Then use the richest callable structured question primitive that can faithfully encode the complete decision. Discover callability and the active primitive's advertised question and option capacities at runtime instead of assuming a harness-wide limit:

- Claude Code: `AskUserQuestion`.
- Codex: `request_user_input` when it is exposed, the active collaboration mode permits it, and the complete gate fits the capacities advertised by that callable primitive.
- Other harnesses: an equivalent structured question primitive with enough option capacity for every action.
- When no structured primitive is callable **or its limits cannot represent every action**: use the lossless numbered-text fallback from the handoff gate. If an active primitive advertises only 2-3 explicit choices, a four-option gate is one case that requires the fallback or a hybrid. A hybrid is valid only if every omitted button remains an explicit, equally actionable numbered choice alongside the structured prompt.

This is a native-first priority order, not a lowest-common-denominator rule. Never merge, hide, or drop actions to fit a host primitive. Preserve the recommended choice, every option's effect or tradeoff, a free-form `Other` path, and immediate execution of the selected non-stop action across every rendering. Degrade only as far as the active harness requires.

## Sub-agent dispatch

Name the semantic contract first:

- fresh context or same context
- read-only or write-capable
- full peer or diminished worker
- synchronous return or fire-and-forget
- phase-only or may chain

Then show the host-specific syntax as an example:

- Anthropic Claude Code: `Agent(...)`
- Codex: host-exposed sub-agent capability, such as `collaboration.spawn_agent`
- OMP: `task(...)`

Treat every syntax name as an example. Discover the active host capability and gate on fresh context, tool scope, and synchronous completion rather than a versioned identifier.

## GitHub operations

State the GitHub action first: read PR state, post a reply, push a branch, open a PR. Then name the transport:

- host GitHub primitive when the harness exposes one
- `gh` CLI as the fallback transport
- if neither exists, the skill halts rather than inventing a third path

## Handoff transitions

Slash commands are presentation, not the control model. The portable contract is the structured handoff:

- `status`
- `next`
- `artifact`
- one-line orientation

If a skill can render a slash command, it may do so, but the same transition should also be usable as explicit dispatch data for non-slash hosts. When the handoff is a resume point, `next` names the runnable target; when it is terminal, `next: done` records that the chain is complete.

## Quick checklist

When writing or editing a skill doc:

1. Say the semantic contract first.
2. Use the richest callable structured question primitive that fits every action; otherwise use a lossless numbered or hybrid rendering.
3. Preserve every explicit action, recommendations, option tradeoffs, free-form `Other`, and immediate selected action.
4. Show the bundled or repo-local helper path before the host fallback.
5. Treat `${CLAUDE_SKILL_DIR}` as optional host context, not the required contract.
6. Keep `status`, `next`, and `artifact` as the durable handoff fields.
7. Use the host GitHub primitive when present; use `gh` as the documented fallback.
