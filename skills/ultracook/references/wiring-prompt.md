# Per-wiring task worker prompt template

Loaded by `/ultracook` at Phase 4. Substitute `{id}`, `{slug}`, `{type}`, `{file}`, `{description}`, and `{spec_summary}` before dispatch.

````text
You are performing integration wiring task: {id} for spec {slug}

## Task

Type: {type} (barrel_export | di_registration | route_wiring | event_subscription | config_entry)
File: {file}
Description: {description}

## Constraints

- Touch ONLY the named file.
- 20 tool calls max — this is a small task.
- No business logic — integration only.
- Commit your change via /commit (or git commit) before returning.

## Spec summary

{spec_summary}

## Workflow

1. Read the file to understand the surrounding structure.
2. Apply the integration change via /cheez-write (or host edit tool if cheez-* is
   unavailable).
3. Run the project's quality gate command — STOP and write
   `status: halt: quality gate failed` if it fails.
4. Commit via /commit (or `git commit -m "<conventional message>"`).
5. Write the handoff slug.

## Handoff slug

Write `.cheese/ultracook/{slug}/wiring/{id}.md` with:

```
status: ok | halt: <one-line reason>
next: merge | done
artifact: <path-to-richer-report-if-any>
<one-line orientation: what this wiring task did>
```

## Do NOT

- Modify any file other than {file}.
- Add business logic — wiring is glue only.
- Push or create PRs (the orchestrator handles that).
- Chain forward (the orchestrator owns the chain).
- Retry on failure — write the halt and return; the orchestrator decides retry policy.
````
