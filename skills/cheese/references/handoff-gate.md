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

Before asking, build a structured gate record. The top-level key is
`handoff_gate:` to distinguish it from per-option context payloads
(`handoff_context:` — see below):

```yaml
handoff_gate:
  source_skill: /cook
  id: post-cook-next-step
  prompt: What should happen next?
  recommended: harden-tests
  multi: false
  options:
    - id: harden-tests
      label: Harden tests before review
      description: Strengthen regression coverage before review.
      dispatch: /press <slug>
      context:
        slug: <slug>
        source_report: .cheese/cook/<slug>.md
        flags: []
    - id: modify-decomposition
      label: Modify decomposition
      description: Revise the current decomposition before continuing.
      continue: ask-for-decomposition-change
      context:
        scope: current-skill
    - id: stop
      label: Stop
      description: Leave the pipeline paused without starting another skill.
      dispatch: none
      context:
        reason: leave pipeline paused
```

Every gate must include:

- **Source skill** — the calling workflow skill that owns the gate.
- **ID** — a stable question identifier.
- **Prompt** — one short question.
- **Recommended** — one option ID, or `none`.
- **Multi** — whether multiple option IDs may be selected.
- **Options** — each with a stable **ID**, user-facing **label**, and
  **description** of its effect or tradeoff.
- Exactly one action per option:
  - **Dispatch** — the exact command for a skill transition
    (`/press <slug>`, `/age <slug> --hard`, …), including slug/path/scope and
    propagated flags such as `--hard`.
  - **Continue** — a short identifier for an in-skill action the current skill
    knows how to execute (e.g. `ask-for-decomposition-change`,
    `re-run-decomposer`, `write-manifest-then-seed`).
  - `dispatch: none` — a terminal option (Stop, Pause, Compact) that returns a
    final status and does not start another skill.
- **Context** — any payload the action needs that is not part of the command.
- **On select** — execute the action immediately after the user selects it.

`dispatch: none` is for terminal options only. Options that keep the current
skill running use `continue:`, so the gate reader can distinguish stopping from
continuing within the current skill.

## Render the gate

Project the generic question fields without renaming or inventing values:

```text
question.id = handoff_gate.id
question.prompt = handoff_gate.prompt
question.recommended = handoff_gate.recommended
question.multi = handoff_gate.multi
question.options = handoff_gate.options map { id, label, description }
```

Retain `source_skill`, `dispatch`, `continue`, and `context` in the gate,
keyed by option id. After the shared
[`ask-user-question.md`](ask-user-question.md) transport returns normalized
option IDs, resolve those IDs against the original gate record. This projection
preserves every question field and every action field; host capabilities only
change presentation.

## After the answer arrives

1. Normalize the answer through
   [`ask-user-question.md`](ask-user-question.md).
2. If the selected option has `dispatch: none`, stop with the relevant artifact
   path or pause status.
3. If the selected option has a `continue:` identifier, execute that in-skill
   action immediately.
4. If the selected option has a `dispatch:` command, immediately enter that
   skill with the exact command and context packet.
5. Do not re-run `/cheese` classification unless the selected option explicitly
   says to do so.

## Context payloads

Use context payloads when command-line flags would create an unstable mini-language. Payloads ride alongside the gate under the key `handoff_context:` so the downstream skill can tell them apart from the gate shape itself:

```yaml
handoff_context:
  source_skill: /age
  source_report: .cheese/age/<slug>.md
  selection: "1,3,5"
  resolved_ids: [1, 3, 5]
  wiki_hits:
    - {page: .hallouminate/wiki/adr/foo-001.md, line: 12, why: "prior decision on X"}
```

Examples of when to attach a `handoff_context:` block:

- `/age -> /cure` selection ids travel as context, not as a `--select` flag.
- `/culture -> /cook` carries the compact contract that emerged from discussion.
- `/melt -> upstream skill` carries the interrupted operation and original skill invocation.
- `/cheese -> <target>` carries `wiki_hits` grounded from the wiki corpus at routing time.

`wiki_hits` is the query-time wiki retrieval key — a list of `{page, line, why}` entries grounded from the `repo:<repo>:wiki` corpus when hallouminate is present (probe and degrade contract: [`optional-plugins.md`](optional-plugins.md)). The attaching skill always renders the hits to the user at dispatch so memory use is visible and stale hits can be challenged; when hallouminate is absent, omit the key.

Keep payloads short and factual. If a payload would exceed a compact screenful, write or reference a `.cheese/.../<slug>.md` handoff artifact and pass the path instead.

## Flag propagation

Propagate `--hard` through every runnable downstream option while the flag is in scope. Propagate `--auto` inside documented auto-mode chains and inside `/cheese`'s autonomous-by-default dispatch path (see `skills/cheese/SKILL.md` § Escalation — tier-1 and tier-2 dispatches pre-select the auto variant and run it without a gate unless `--safe` is set).

Propagate `--safe`, `--open-pr`, and `--hard` through runnable implementation options. `--open-pr` reaches terminal `/plate`; it authorizes new-PR publication but does not override an explicit topology choice or waive a question required by `/plate`'s review-shape policy. `--hard` is consumed by `/plate` after its final artifact-writing gate.

Outside those autonomous paths, interactive gates must not add `--auto` unless the option explicitly says `--auto` and the user selected it. Inside them, the auto variant is the pre-selected recommended target by design — `--safe` is the user's opt-out to a gated flow, where the auto variant remains pre-selected but dispatch waits for confirmation.

## Standard forward-step menu

The forward command and label vary per gate. A simple menu contains four options by design, not a host or button cap: one forward step plus the standard tail (**Plate it**, **Checkpoint & stop**, **Stop**).

- **<forward verb>** *(recommended)* — one interactive downstream phase.
- **Plate it** — run the remaining pipeline headless, then dispatch `/plate`; a new PR follows its explicit-choice and review-shape policy.
- **Checkpoint & stop** — `/wheypoint`.
- **Stop** — `dispatch: none`.

Propagate in-scope `--hard` and `--open-pr`. `/plate`, not an upstream auto chain, owns final durable writes, commit, topology resolution, any required question, and publication.

When a gate carries a richer *core* decision, keep every gate-specific alternative as an explicit `handoff_gate.options` record, then append the
standard tail. The shared question transport decides whether to use structured
controls or the numbered fallback; no alternative is demoted to prose or
`Other`.
