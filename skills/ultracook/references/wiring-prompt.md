# Per-wiring task worker prompt template

Loaded by `/ultracook` at Phase 4. Substitute `{id}`, `{slug}`, `{type}`, `{file}`, `{description}`, `{spec_summary}`, and `{agent_resolution}` before dispatch.

````text
You are performing integration wiring task: {id} for spec {slug}

Resolved role: coder
Agent resolution: {agent_resolution}

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
3. Run the project's quality gate. If it fails, commit `status: halt` with `halt_reason: quality gate failed`.
4. Commit via `/plate` commit-only mode only after a green gate.
5. Join the inherited WorkRecord and commit the wiring result through the shared `skills/cheese/references/work-contract.md` transaction. Return the runtime-derived artifact path and preserve `{agent_resolution}` in provenance. Do not hand-write a flat handoff file.

## Do NOT

- Modify any file other than {file}.
- Add business logic — wiring is glue only.
- Push or create PRs (the orchestrator handles that).
- Chain forward (the orchestrator owns the chain).
- Retry on failure — write the halt and return; the orchestrator decides retry policy.
````
