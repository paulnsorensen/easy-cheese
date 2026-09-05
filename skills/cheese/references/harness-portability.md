# Harness Portability

Use this reference for host capability descriptions.
Helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions are capability contracts.
Name the contract before you show a host example.

## Helper resolution

Prefer bundled or repo-local paths.
They work on every host:

- `src/easy_cheese/shared/*.py` for repo-wide helpers such as corpus path resolution, handoff artifact writing, and slug readers.
- `skills/<skill>/scripts/*.pyz` for skill-specific helpers bundled with the repo.

Do not use the `${CLAUDE_SKILL_DIR}` environment variable in invocation paths.
Claude Code substitutes it, but Codex CLI does not.
Codex receives the literal variable and fails.

Name the behavior that a helper provides.
Do not imply that one absolute path is the only valid transport.

## Read, search, edit, inspect

Use the host primitive that preserves bounded context.
When the host offers several primitives, prefer the one that returns fresh line or snapshot context.
Name every other primitive as a fallback only.

## User interaction

Build the semantic question before selecting a transport. Generic questions use
the shared [`ask-user-question.md`](ask-user-question.md) contract. Workflow
handoffs first build the semantic record defined by
[`handoff-gate.md`](handoff-gate.md), then render that record through
`ask-user-question.md`.

The question reference owns capability detection, lossless fallbacks, batching,
defaults, and answer normalization. Per-harness tool names live in its
maintainer sources appendix, not in any runtime path. Keep those details out of
workflow skills and this portability overview.

## Sub-agent dispatch

Name the semantic contract first:

- fresh context or same context
- read-only or write-capable
- minimum power (`cheap | default | powerful`) and whether the selection is `degraded`
- synchronous return or fire-and-forget
- phase-only or may chain

Then show the host-specific syntax as an example:

- Anthropic Claude Code: `Agent(...)`
- Codex: host-exposed sub-agent capability, such as `collaboration.spawn_agent`
- OMP: `task(...)`

Treat each syntax name as an example.
Discover the active host capability.
Require fresh context, correct tool scope, and synchronous completion.

[`agent-resolution.md`](agent-resolution.md) defines selection, minimum power, fallbacks, permission degradation, and artifact provenance.
Use that resolver before you render host-specific dispatch.

## GitHub operations

State the GitHub action first.
Then name the transport:

- host GitHub primitive when the harness exposes one
- `gh` CLI as the fallback transport
- if neither exists, the skill halts rather than inventing a third path

## Handoff transitions

Slash commands are presentation, not the control model. The portable contract is the structured handoff:

- `status`
- `next`
- `artifact`
- one-line orientation

A slash command can render a transition.
The same transition must also work as explicit dispatch data.
At a resume point, `next` names the runnable target.
At a terminal point, `next: done` records completion.

## Quick checklist

When writing or editing a skill doc:

1. Say the semantic contract first.
2. Use the richest callable structured question primitive that fits every action; otherwise use a lossless numbered or hybrid rendering.
3. Preserve every explicit action, recommendations, option tradeoffs, free-form `Other`, and immediate selected action.
4. Show the bundled or repo-local helper path before the host fallback.
5. Use repo-relative paths (`skills/<skill>/scripts/...`), not `${CLAUDE_SKILL_DIR}` — the latter is Claude Code-specific.
6. Keep `status`, `next`, and `artifact` as the durable handoff fields.
7. Use the host GitHub primitive when present; use `gh` as the documented fallback.
