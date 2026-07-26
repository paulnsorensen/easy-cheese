# Cross-skill work contract

WorkRecord is the continuation authority. Phase artifacts are journaled evidence linked from that record; modification time, readable slug, and session identity never select work.

## Enter work

A meaningful direct workflow creates a record. A nested workflow joins the inherited work ID:

```bash
python3 skills/cheese/scripts/cheese.pyz work ensure --subject "<meaningful subject>"
python3 skills/cheese/scripts/cheese.pyz work ensure --work-id "<inherited work_id>"
```

Read `work_id`, the current worktree's nonterminal `attempt_id`, and `revision` from the JSON result. Do not create a second record in a nested phase. A routing or continuation call with neither a work ID nor a meaningful subject creates nothing.

## Continue work

Bare continuation asks the runtime for the deterministic candidate set:

```bash
python3 skills/cheese/scripts/cheese.pyz work continue
```

For `action: continue`, resume the sole returned record. For `action: picker`, show the returned `records` as a numbered picker in their existing order. Zero worktree candidates produce the project-wide picker; two or more worktree candidates produce the worktree-scoped picker. Never choose by file time, revision, or list position. The runtime imports a local-only `.cheese/work/<work-id>/index.md` snapshot into durable storage and rejects divergent local and durable copies for explicit reconciliation.

An explicit legacy note path is migration input, not a competing continuation authority:

```bash
python3 skills/cheese/scripts/cheese.pyz work migrate "<legacy-note-path>"
python3 skills/cheese/scripts/cheese.pyz work continue
```

The migration preserves the source and reports malformed or ambiguous input under `skipped`.

## Commit a handoff

First validate the installed global registry:

```bash
python3 skills/cheese/scripts/cheese.pyz contract-registry validate
```

Allocate one `op_<uuid4>` before rendering. Send one JSON object to `handoff-commit`; do not write frontmatter or derive the artifact path yourself:

```json
{
  "phase": "cook",
  "slug": "readable-slug",
  "work_id": "wk_<uuid4>",
  "attempt_id": "wa_<uuid4>",
  "expected_revision": 7,
  "next_phase": "press",
  "status": "ok",
  "halt_reason": null,
  "payload": {},
  "provenance": {"inputs": []},
  "work_patch": {"scope": "work", "changes": []},
  "body": "# Cook Report — readable-slug\n\n<phase-owned report body>\n",
  "operation_id": "op_<uuid4>"
}
```

```bash
python3 skills/cheese/scripts/cheese.pyz handoff-commit < request.json
```

Use `scope: work` only for shared working context, decisions, parked items, or open questions. Use `scope: attempt` with the matching `attempt_id` only for attempt context. Empty changes are valid. Put phase-specific metadata in `payload` according to `skills/<phase>/references/handoff-contract.yaml`; keep the full Markdown report in `body`.

The runtime derives `.cheese/<phase>/<work-id>/<operation-id>-<slug>.md`, validates the envelope and payload, journals the operation, promotes the artifact, patches the record, and returns the committed artifact path. On interruption, retry the exact same request and operation ID. Reusing that ID with changed content is rejected.

## Resolve the destination

Pass the committed artifact and the phase names actually callable in the current harness:

```json
{"artifact": "<committed artifact path>", "available_phases": ["cook", "press", "age", "cure"]}
```

```bash
python3 skills/cheese/scripts/cheese.pyz handoff-resolve < resolution.json
```

Act only on the returned action:

- `halt`: report `reason` and retain `next` as the resumable destination; do not dispatch until the user explicitly resumes.
- `dispatch`: invoke the returned phase and propagate `work_id`.
- `unavailable`: report the retained phase as unavailable; do not block or rewrite the WorkRecord.
- `done`: report terminal state; never dispatch `done`.
- `hold`: pause without dispatch.
- `tasks`: use the persisted ordered task directives; never dispatch `tasks` as a phase.

If the companion runtime is absent, halt with exactly: `Cheese contract runtime is required; install easy-cheese's Cheese companion runtime`.
