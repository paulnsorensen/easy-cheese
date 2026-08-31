# Per-wiring task worker prompt template

Loaded by the `/cook` fan pathway at Phase 4. Substitute `{id}`, `{slug}`, `{type}`, `{file}`, `{description}`, `{spec_summary}`, `{model}`, `{effort}`, and `{agent_resolution}` before dispatch.

`{model}` and `{effort}` are resolved for the wiring task's role (coder), per `skills/cheese/references/agent-resolution.md` § Phases x roles. They are never left unsubstituted so the spawn falls through to the parent's model.

````text
You are performing integration wiring task: {id} for spec {slug}

Resolved role: coder
Agent resolution: {agent_resolution}

## Model

Model: {model}
Effort: {effort}

This task runs at the model and effort resolved for its role, not at whatever model the dispatching parent is running. A wiring task never silently inherits the parent model: if `{model}` arrived unresolved, halt rather than guessing one. The resolved model, power, and effort are recorded in `agent_resolution` (`resolved.model`, `resolved.power`, `resolved.effort`) and copied unchanged into the handoff slug below.

## Task

Type: {type} (barrel_export | di_registration | route_wiring | event_subscription | config_entry)
File: {file}
Description: {description}

## Constraints

- Touch ONLY the named file.
- 20 tool calls max — this is a small task.
- No business logic — integration only.
- Commit your change via `/plate` commit-only mode before returning.

## Spec summary

{spec_summary}

## Workflow

1. Read the file with the backend that will validate the write anchor.
2. Apply the integration change through a stale-safe edit according to `skills/cheese/references/code-intelligence-routing.md`.
3. Run the project's quality gate command — STOP and write
   `status: halt: quality gate failed` if it fails.
4. Commit via `/plate` commit-only mode.
5. Write the handoff slug.

## Handoff slug

Write `.cheese/ultracook/{slug}/wiring/{id}.md` with:

```
status: ok | halt: <one-line reason>
next: merge | done
artifact: <path-to-richer-report-if-any>
<one-line orientation: what this wiring task did>
agent_resolution: {agent_resolution}
```

## Do NOT

- Modify any file other than {file}.
- Add business logic — wiring is glue only.
- Push or create PRs (the orchestrator handles that).
- Chain forward (the orchestrator owns the chain).
- Retry on failure — write the halt and return; the orchestrator decides retry policy.
````
