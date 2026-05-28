# Handoff gate

Use this reference whenever a workflow skill asks the user to choose the next step after a gate.

## Contract

A handoff gate prevents silent dispatch. It does not mean the agent stops after the user selects an option. Once the user chooses a non-stop option, the current assistant turn immediately starts the selected action — either dispatching a downstream skill (skill transition) or continuing internal work in the current skill (in-skill continuation).

"Never auto-invoke" means no downstream skill starts before an explicit user selection. It is not permission to answer only with "next: /some-skill" after the user has already selected that option.

## Vocabulary

- **Dispatch** — start a *new* skill with a concrete command. Reserved for skill transitions.
- **Continue / proceed** — keep working inside the *current* skill (e.g. write a manifest, ask one targeted follow-up, re-run an internal phase). Never write `dispatch:` for in-skill continuation; use `continue:` instead.
- **Stop / pause** — return a final status with no further action.

## Gate shape

Before asking, render each option as a structured record. The host UI may show this as buttons, a structured question, or a numbered list, but the semantics must be stable. The top-level key is `handoff_gate:` to distinguish it from per-option context payloads (`handoff_context:` — see below):

```yaml
handoff_gate:
  source_skill: /<current-skill>
  recommended: <label-or-none>
  options:
    - label: Run /press <slug>
      dispatch: /press <slug>
      context:
        slug: <slug>
        source_report: .cheese/cook/<slug>.md
        flags: []
    - label: Modify decomposition
      continue: ask-for-decomposition-change
      context:
        scope: current-skill
    - label: Stop
      dispatch: none
      context:
        reason: leave pipeline paused
```

Every option must include:

- **Label** — the user-facing choice.
- Exactly one of:
  - **Dispatch** — the exact command for a skill transition (`/press <slug>`, `/age <slug> --hard`, …), including slug/path/scope and propagated flags such as `--hard`.
  - **Continue** — a short identifier for an in-skill action the current skill knows how to execute (e.g. `ask-for-decomposition-change`, `re-run-decomposer`, `write-manifest-then-seed`).
  - `dispatch: none` — terminal options (Stop, Pause, Compact) that return a final status and do not start another skill.
- **Context** — any prose or structured payload the action needs but that is not part of the command line.
- **On select** — execute the dispatch or continue action immediately after the user selects it.

`dispatch: none` is for *terminal* options only. Options that keep the current skill running must use `continue:`, not `dispatch: none`, so the gate reader can tell "stop" apart from "do something else in this skill".

## Codex-compatible asking

Prefer the host's structured question primitive when it is callable (`AskUserQuestion`, Codex `request_user_input`, or the host equivalent). If no structured primitive is available, ask a plain numbered question and wait for the next user reply.

After the answer arrives:

1. Normalize the answer to one option label or recognized free-text verb.
2. If the answer is ambiguous, ask one clarifying question; do not guess.
3. If the selected option has `dispatch: none`, stop with the relevant artifact path or pause status.
4. If the selected option has a `continue:` identifier, execute that in-skill action immediately.
5. If the selected option has a `dispatch:` command, immediately enter that skill with the exact command and context packet.
6. Do not re-run `/cheese` classification unless the selected option explicitly says to do so.

## Context payloads

Use context payloads when command-line flags would create an unstable mini-language. Payloads ride alongside the gate under the key `handoff_context:` so the downstream skill can tell them apart from the gate shape itself:

```yaml
handoff_context:
  source_skill: /age
  source_report: .cheese/age/<slug>.md
  selection: "1,3,5"
  resolved_ids: [1, 3, 5]
```

Examples of when to attach a `handoff_context:` block:

- `/age -> /cure` selection ids travel as context, not as a `--select` flag.
- `/culture -> /cook` carries the compact contract that emerged from discussion.
- `/melt -> upstream skill` carries the interrupted operation and original skill invocation.

Keep payloads short and factual. If a payload would exceed a compact screenful, write or reference a `.cheese/.../<slug>.md` handoff artifact and pass the path instead.

## Flag propagation

Propagate `--hard` through every runnable downstream option while the flag is in scope. Propagate `--auto` inside documented auto-mode chains and inside `/cheese`'s autonomous-by-default dispatch path (see `skills/cheese/SKILL.md` § Escalation — tier-1 and tier-2 dispatches pre-select the auto variant and run it without a gate unless `--safe` is set).

Outside those autonomous paths, interactive gates must not add `--auto` unless the option explicitly says `--auto` and the user selected it. Inside them, the auto variant is the pre-selected recommended target by design — `--safe` is the user's opt-out to a gated flow, where the auto variant remains pre-selected but dispatch waits for confirmation.
