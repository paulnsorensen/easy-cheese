# Cross-skill work contract

Status: approved; serialization amendment accepted 2026-07-26
Source: promoted from the Mold artifact at `$XDG_DATA_HOME/cheese/paulnsorensen-easy-cheese/specs/cross-skill-work-contract.md`

This specification makes one `WorkRecord` the deterministic continuation authority for a user work item. Phase artifacts become validated, operation-scoped evidence around that record. Persisted runtime state uses JSON object frontmatter inside Markdown; human-authored phase contracts remain YAML build inputs; released bundles contain no PyYAML.

## Problem

Cross-skill handoffs are prose conventions parsed by helpers that accept a smaller and partly contradictory contract. Multiline values, repeated durable flags, phase-specific fields, Wheypoint provenance, and writer-owned paths do not share one validated model.[^1] Continuation infers recent work from artifacts rather than preserving the user's connective context across phases, conversations, and concurrent worktrees.[^2]

PR #331 implemented part of the earlier design but also bundled PyYAML into `cheese.pyz`, left public task lifecycle operations unwired, allowed blocked attempts to bypass explicit unblocking, accepted overly broad legacy input, and did not cover the full acceptance set. This tracked specification is the implementation authority for the replacement stack.[^3]

## Goals

- Establish one versioned, machine-validated handoff envelope for cross-skill boundaries.
- Preserve phase ownership through small phase-specific payload contracts and outgoing-transition declarations.
- Maintain one living `WorkRecord` for each user work item, with branch/worktree execution represented by `WorkAttempt`.
- Make bare continuation deterministic without session identity, foreground pointers, timestamps, or model inference.
- Preserve freeform working context, decisions, parked items, open questions, research links, and interruption history.
- Make artifact and work-record updates concurrency-safe, idempotent, and recoverable.
- Keep the released runtime on Python 3.10+ and the standard library only.
- Keep source-authored `PhaseContract` declarations readable YAML while using PyYAML only during bundle construction.
- Migrate unambiguous legacy artifacts conservatively while preserving originals.

## Non-goals

- Invocation-input schemas; this specification covers boundaries between skills only.
- Full report-body schemas; Markdown report bodies remain phase-owned prose.
- Remote or cross-machine synchronization. Harnesses share continuity only when they share the same user filesystem and XDG data root.
- Model-assisted legacy inference or semantic merging.
- Caller authentication or a security boundary between foreground and background agents.
- Automatic two-way synchronization of durable records and repo-local snapshots.
- Changing Agent Skills frontmatter or other repository-authored YAML metadata to JSON.

## Serialization boundary

Persisted `HandoffEnvelope` and `WorkRecord` documents use a JSON object between `---` fences followed by a Markdown body. The runtime parses and renders that object with Python's standard-library `json` module.

```markdown
---
{
  "contract_version": "cheese-handoff/v1",
  "work_id": "wk_<uuid4>",
  "attempt_id": "wa_<uuid4>",
  "operation_id": "op_<uuid4>",
  "phase": "cook",
  "status": "ok",
  "halt_reason": null,
  "next": "press",
  "artifact": ".cheese/cook/wk_<uuid4>/op_<uuid4>-example.md",
  "payload": {},
  "provenance": {"inputs": []}
}
---
# Cook report
```

This is JSON frontmatter, not YAML-in-JSON and not an unrestricted YAML document. JSON's syntax is intentionally accepted as the persisted contract because it is deterministic, strict, and available without a third-party runtime dependency.

Human-authored `skills/<phase>/references/handoff-contract.yaml` declarations remain YAML. Build tooling installs the pinned PyYAML version, validates and compiles those declarations into a JSON-compatible registry, and embeds only the compiled registry in `skills/cheese/scripts/cheese.pyz`. The released archive must not contain `yaml/`, a vendored PyYAML license, or an ambient PyYAML dependency.

## Storage and identity

Persist each user work item at:

```text
$XDG_DATA_HOME/cheese/<project>/work/<work-id>/index.md
```

An optional portable snapshot may exist at:

```text
<worktree>/.cheese/work/<work-id>/index.md
```

The durable record is canonical. The local file is an explicitly exported or user-committed snapshot. Discovery inspects both.

Every phase artifact path is derived from `phase`, `work_id`, `operation_id`, and a readable slug:

```text
<worktree>/.cheese/<phase>/<work-id>/<operation-id>-<slug>.md
```

The operation ID is allocated before rendering. Retrying the same operation resolves the same path; different operations or WorkRecords cannot overwrite one another when their slugs match.

`WorkRecord` owns shared working context. `WorkAttempt` owns branch/worktree-specific progress and tentative findings. Every context patch declares `scope: work | attempt`. Phase artifacts remain specialized evidence linked from the record rather than replacing it.

Identifiers use UUID4 values with `wk_`, `wa_`, and `op_` prefixes. `WorktreeKey` derives from the absolute worktree-specific Git directory, never branch name or cwd.

## Handoff envelope

The envelope owns:

- `contract_version`, `work_id`, `attempt_id`, and `operation_id`;
- source `phase`;
- `status: ok | halt` and conditional `halt_reason`;
- `next`, which is a registered phase or `done | hold | tasks`;
- the normalized current `artifact` path;
- phase-owned `payload`;
- bounded `provenance`.

The `artifact` field identifies the file containing the envelope and must equal the loaded path after normalization. Upstream evidence belongs in `payload.inputs` or `provenance`, never in `artifact`.

`halt_reason` is required and non-empty when status is `halt`, and must be null or absent for `ok`. A halt does not implicitly change WorkRecord lifecycle status.

`done` completes the current WorkAttempt; the WorkRecord completes only when it has no nonterminal attempts or tasks. `hold` pauses the attempt. `tasks` keeps it active and requires a non-empty ordered `payload.tasks` list. Reserved outcomes are never phase declarations or dispatch targets.

Phase payload contracts use a bounded vocabulary: mapping, list, string, integer, boolean, nullability, required fields, and nested fields. Arbitrary JSON Schema features are out of scope.

## Work record

A WorkRecord document begins with JSON frontmatter:

```json
{
  "schema_version": "cheese-work/v1",
  "work_id": "wk_<uuid4>",
  "slug": "readable-alias",
  "title": "Human-readable work item",
  "project_key": "owner-repository",
  "status": "active",
  "revision": 7,
  "attempts": [
    {
      "attempt_id": "wa_<uuid4>",
      "worktree_key": "wt_<digest>",
      "status": "active",
      "current_phase": "mold",
      "artifacts": []
    }
  ],
  "tasks": []
}
```

The lifecycle is closed: `active | paused | blocked | completed | abandoned`.

The Markdown body contains these stable sections:

```markdown
# <title>

## Working context
<curated shared context>

## Decisions
<accepted shared decisions>

## Parked
<parked items and useful research>

## Open questions
<unresolved questions>

## Attempts
### <attempt-id>
<branch/worktree-specific context>

## Context log
<append-only material-context events>
```

Python appends context-log entries. Agents may replace curated context only through a revision-checked patch.

## Context patches

A `WorkPatch` is a closed discriminated JSON mapping:

```json
{
  "scope": "work",
  "changes": [
    {
      "section": "working_context",
      "operation": "append",
      "value": "Markdown string"
    }
  ]
}
```

For work scope, `attempt_id` is absent and sections are `working_context | decisions | parked | open_questions`. For attempt scope, `attempt_id` is required, must equal the envelope attempt, and the only section is `attempt_context`. Operations are `replace | append`. Empty changes are valid. Unknown keys, sections, or operations fail validation.

Artifact linkage and lifecycle are runtime-derived, not caller-controlled patch fields. A successful `commit_handoff` appends an idempotent artifact reference containing normalized path, phase, and operation ID. Registered phase destinations activate the attempt and update `current_phase`; `done` completes it; `hold` pauses it; `tasks` stores validated pending tasks. Contradictory caller patches are unrepresentable.

## Attempt, task, and work lifecycle

Context edits and lifecycle edits are separate. An `AttemptStatePatch` carries `attempt_id`, `target_status: active | paused | blocked | abandoned`, and an optional reason. A non-empty reason is required for `blocked` and `abandoned` and forbidden otherwise. Active, paused, and blocked attempts may transition among those states or to abandoned. Completed and abandoned attempts are terminal. Clearing a block requires an explicit revision-checked transition to active or paused.

Each task directive requires a registered destination `phase`, a non-empty `subject`, and an optional bounded mapping named `input`. The runtime validates only that shape. On commit, Python derives a stable task ID from the handoff operation ID and directive index, preserving order, and stores it pending.

`claim_task` atomically changes one pending task to active and binds it to the claiming WorkAttempt. A successful handoff carrying that task ID verifies the bound attempt and phase, then completes the task in the same journaled mutation. Replay is idempotent. An explicit revision-checked task transition may block, return to pending, or abandon a pending, active, or blocked task. Completed and abandoned tasks are terminal.

A WorkRecord completes only when all attempts and tasks are terminal. `done` may complete one attempt while the record remains active.

WorkRecord status is stored but derived after every mutation. Explicit `abandon_work` requires a reason, atomically abandons all nonterminal attempts and tasks, and wins over aggregate state. Otherwise:

1. active when any attempt is active or task is pending/active;
2. blocked when nonterminal items exist and all are blocked;
3. paused when nonterminal items exist, none is active/pending, and at least one attempt is paused;
4. completed when no nonterminal item remains.

Individually abandoned children do not abandon the record. Completed and abandoned records do not reopen through join or inherited phase input. Explicit revision-checked `reopen_work` preserves history, clears abandonment state, and creates one active attempt for the current WorktreeKey.

## Creation and update rules

- An existing `work_id` joins that record.
- For the current WorktreeKey, reuse its single active, paused, or blocked attempt.
- When the record is nonterminal and no nonterminal attempt exists, create a new active attempt.
- Completed or abandoned records remain unchanged until explicit reopen.
- At most one nonterminal WorkAttempt may exist per WorktreeKey.
- No `work_id` plus a meaningful subject creates a record for every meaningful direct workflow.
- No `work_id` and no subject creates nothing; empty routing and continuation remain read-only.
- Nested/background phases inherit `work_id`; Python does not infer caller role.
- Material context updates occur at entry/exit, phase changes, research detours, accepted decisions, parking, and interruption, not every conversational turn.

## Continuation and snapshots

For the current project and WorktreeKey, resolve active or paused candidates as a set:

```text
0 worktree candidates  -> project-wide numbered picker
1 worktree candidate   -> continue automatically
2+ worktree candidates -> worktree-scoped numbered picker
```

Selection never uses modification time, revision recency, or update order. Picker ordering is deterministic by status, title, then work ID.

Discovery unions durable storage and the current worktree snapshot:

- durable only: continue from durable;
- local only: validate and import, preserving ID and provenance;
- byte-identical logical records: continue from durable;
- divergent copies: stop for explicit reconciliation;
- different IDs: distinct candidates.

Revision numbers alone never establish ancestry. Python rewrites a local snapshot only through explicit export or synchronization.

## Transactions and recovery

A handoff commit executes:

1. Render and validate the artifact in a unique temporary file.
2. Acquire the project/work-record lock.
3. Verify the expected work revision.
4. Write a prepared operation-journal entry keyed by `operation_id` and a fingerprint of the request.
5. Atomically promote the artifact.
6. Apply the scoped WorkRecord mutation and increment revision atomically.
7. Mark the operation complete and release the lock.

A stale revision rejects before promotion. Reusing an operation ID with an identical request returns the original result; reusing it with changed request content is rejected. If execution stops after promotion but before record update, reconciliation may apply only the recorded mutation and never invents context.

## Registry and harness availability

The source phase owns outgoing transitions; the build assembles and validates the global registry. Every globally addressable destination declares a PhaseContract, including destinations with no outgoing transitions.

Unknown phases, disallowed transitions, invalid payloads, duplicate phase declarations, malformed contracts, and unsupported schema constructs fail global validation.

A globally valid phase absent from the current harness remains persistable. Resolution reports it unavailable and does not dispatch. Work does not become blocked merely because another harness owns that phase.

## Legacy migration

Migration is Python-only and bounded:

- parse only recognized legacy headers and headings;
- reject files containing unrecognized preamble or structure rather than accepting arbitrary trailing text as a handoff;
- map `status: ok` directly;
- map `status: halt: <reason>` to `halt` plus the same reason while retaining runnable `next`;
- map `status: gated: <decision>` to `halt`, the decision as reason, and `next: hold`, preserving the proposed destination in provenance;
- convert recognized Wheypoint list-form `next` to `next: tasks` plus ordered directives;
- validate slugs and paths with shared path helpers;
- copy the complete legacy body under imported context;
- preserve original paths, files, and migration provenance;
- group artifacts only through explicit recognized artifact/provenance links;
- never group by slug, timestamps, prose similarity, or model judgment;
- leave malformed or ambiguous items unmigrated and report candidates.

Duplicate imported records are preferable to silently combining unrelated work.

## Packaging

`/cheese` is the mandatory companion runtime for contract-aware workflow skills. Other skills invoke sibling `skills/cheese/scripts/cheese.pyz`; absence fails with the exact instruction: `Cheese contract runtime is required; install easy-cheese's Cheese companion runtime`.

Maintainers and CI install the exact pinned PyYAML build dependency. The bundler uses it only to validate source `handoff-contract.yaml` files and compile the global registry. The released `cheese.pyz` contains standard-library runtime code plus the compiled registry, and no vendored PyYAML package or license. `python3 -S` proves handoff and WorkRecord JSON round trips and registry loading without ambient packages.

The shared companion intentionally replaces per-consumer `common.pyz` duplication, but it does not create a second dependency policy for released Easy Cheese skills.

## Acceptance

- WHEN a workflow receives an existing work ID THE SYSTEM SHALL join that WorkRecord without creating another.
- WHEN a nonterminal WorkRecord has no nonterminal WorkAttempt for the current WorktreeKey THE SYSTEM SHALL create one while preserving history.
- WHEN one active, paused, or blocked attempt exists for the WorktreeKey THE SYSTEM SHALL reuse it and SHALL NOT duplicate it; blocked remains blocked until explicitly patched.
- WHEN handoff status is `halt` THE SYSTEM SHALL require a non-empty structured reason without implicitly changing lifecycle state.
- WHEN `next` is `done` THE SYSTEM SHALL complete the current attempt without treating `done` as a phase.
- WHEN `next` is `hold` THE SYSTEM SHALL pause the current attempt without dispatch.
- WHEN `next` is `tasks` THE SYSTEM SHALL require non-empty ordered structured directives and SHALL NOT dispatch `tasks` as a phase.
- WHEN an attempt is blocked or abandoned THE SYSTEM SHALL require a revision-checked patch with a non-empty reason; clearing a block SHALL be explicit; terminal attempts SHALL remain terminal.
- WHEN a task directive is committed THE SYSTEM SHALL validate its registered phase, non-empty subject, and optional bounded input; derive a stable ordered ID; and mutate it through revision-checked journaled operations.
- WHEN a handoff carries an active task ID THE SYSTEM SHALL verify bound attempt and phase and complete the task exactly once in the same transaction.
- WHEN record status is recomputed THE SYSTEM SHALL apply the specified active, blocked, paused, completed precedence unless explicit abandonment overrides it.
- WHEN work is abandoned THE SYSTEM SHALL atomically abandon nonterminal children with a reason; ordinary joins SHALL NOT reopen completed or abandoned records.
- WHEN explicit `reopen_work` targets completed or abandoned work THE SYSTEM SHALL preserve history, create one active attempt for the WorktreeKey, clear abandonment state, and derive active status.
- WHEN a globally addressable workflow has no outgoing transitions THE SYSTEM SHALL still register it as a valid destination.
- WHEN a workflow has no work ID but has a meaningful subject THE SYSTEM SHALL create a WorkRecord and WorkAttempt.
- WHEN a routing or continuation command has neither work ID nor subject THE SYSTEM SHALL create nothing.
- WHEN an expected revision is stale THE SYSTEM SHALL reject without artifact or record promotion.
- WHEN an operation ID is replayed with changed request content THE SYSTEM SHALL reject it rather than return the earlier result.
- WHEN phase, transition, payload, or declared artifact path is globally invalid THE SYSTEM SHALL reject before persistence.
- WHEN an artifact path is derived THE SYSTEM SHALL namespace it by phase, WorkRecord ID, and operation ID.
- WHEN a globally valid destination is unavailable locally THE SYSTEM SHALL persist and report unavailable without changing lifecycle state.
- WHEN artifact promotion succeeds but record update does not THE SYSTEM SHALL reconcile the recorded operation exactly once.
- WHEN exactly one active or paused record belongs to the WorktreeKey THE SYSTEM SHALL continue automatically.
- WHEN multiple active or paused records belong to the WorktreeKey THE SYSTEM SHALL return a numbered picker and SHALL NOT choose by recency.
- WHEN no active or paused record belongs to the WorktreeKey THE SYSTEM SHALL return project-wide active or paused candidates.
- WHEN a valid local snapshot lacks a durable copy THE SYSTEM SHALL import it preserving identity and provenance.
- WHEN durable and local copies diverge THE SYSTEM SHALL require reconciliation and SHALL NOT prefer timestamp or revision.
- WHEN a nested phase receives a work ID THE SYSTEM SHALL patch it without inferring foreground/background caller identity.
- WHEN a legacy artifact is malformed, structurally unrecognized, or ambiguously related THE SYSTEM SHALL preserve it and decline migration.
- WHEN phase contracts compile THE SYSTEM SHALL reject duplicate phases, unknown destinations, malformed schemas, and unsupported payload constructs.
- WHEN `cheese.pyz` runs under `python3 -S` THE SYSTEM SHALL load the compiled registry and round-trip persisted JSON frontmatter without ambient packages.
- WHEN the release archive is inspected THE SYSTEM SHALL contain neither vendored PyYAML code nor its bundled license.
- WHEN a contract-aware phase cannot locate `/cheese` THE SYSTEM SHALL fail with the exact companion installation instruction.
- WHEN two harnesses share an XDG data root THE SYSTEM SHALL observe the same WorkRecords regardless of phase availability.
- WHEN task lifecycle is used through `/cheese` THE SYSTEM SHALL expose stable task IDs and public claim, block, return-to-pending, abandon, and task-bound handoff operations.

## Public interfaces

```text
paths.py
  work_record_path(work_id, project=None) -> Path
  local_work_snapshot_path(work_id, repo_root=None) -> Path
  worktree_key(repo_root=None) -> str

work.py / work_cli.py
  ensure_work(...)
  load_work(...)
  patch_work(...)
  list_work(...)
  resolve_continue(...)
  export_work_snapshot(...)
  migrate_legacy(...)
  reconcile_work(...)
  transition_attempt(...)
  claim_task(...)
  transition_task(...)
  abandon_work(...)
  reopen_work(...)

handoff.py
  parse_handoff(text, loaded_path)
  render_handoff(envelope, body)
  validate_handoff(envelope, contracts)
  assemble_transition_registry(contract_paths)

write_handoff_artifact.py
  commit_handoff(..., task_id=None, operation_id=None)
```

CLI requests read JSON from stdin and emit JSON to stdout. Persisted records and handoffs use JSON object frontmatter plus Markdown bodies. Phase contract source files remain YAML.

## Review stack

The implementation is split in dependency order. Every layer must pass `just check` cumulatively.

1. **spec-and-adrs** — this specification, domain model, and three decisions.
2. **handoff-envelope-registry** — JSON envelope parsing/rendering, YAML source PhaseContracts, compiled registry, validation, and tests.
3. **work-record-runtime** — durable WorkRecord/WorkAttempt/WorkTask persistence, paths, lifecycle, continuation, snapshots, migration, and tests.
4. **atomic-handoff-commit** — revision-checked artifact/record transaction, operation fingerprinting, recovery, task completion, and tests.
5. **cheese-runtime-packaging** — standard-library Cheese runtime, build-only PyYAML contract compilation, removal of consumer duplication, archive checks, and tests.
6. **workflow-contract-adoption** — direct-entry work creation/join, inherited nested work, public task dispatch, continuation, exact diagnostics, docs, and tests.

## Quality gates

- `just check` passes for every cumulative stack layer.
- `python3 -S skills/cheese/scripts/cheese.pyz contract-registry validate` passes.
- Core work, handoff, migration, transaction, packaging, and workflow adoption tests map to every acceptance statement above.

## Decisions

- Use a base envelope plus phase-owned payload contracts rather than one universal payload or prose-only conventions.
- Use a living WorkRecord rather than continuation inferred from the latest artifact.
- Use stable work identity plus WorkAttempts rather than branch, worktree, slug, or session identity.
- Remove session keys and mutable foreground/worktree pointers; candidate cardinality is the only automatic continuation rule.
- Separate shared WorkRecord context from WorkAttempt context through explicit patch scope.
- Treat locally missing phases as dispatch limitations, not invalid contracts.
- Register destination-only workflows and reserve `done`, `hold`, and `tasks` as structured non-phase outcomes.
- Use conservative migration and explicit reconciliation rather than inferred joins or merges.
- Use JSON object frontmatter for persisted runtime state rather than runtime YAML, sidecar JSON, SQLite, or a custom YAML subset.
- Keep human-authored PhaseContracts in YAML and PyYAML in the build environment only; ship neither PyYAML code nor license.
- Make `/cheese` the required shared runtime rather than duplicating runtime code into every phase.
- Treat repo-local work files as optional portable snapshots, not co-authoritative stores.

## References

[^1]: `shared/scripts/handoff.py:45-49,87-116`; `skills/cook/SKILL.md:224-231`; `skills/age/SKILL.md:191-203,248-260`; `skills/pasteurize/SKILL.md:160-176`; `.hallouminate/wiki/adr/wheypoint-provenance-schema-001.md:31-38`.
[^2]: `skills/cheese/SKILL.md:89-114`; `skills/wheypoint/SKILL.md:74-85`; [Git worktree documentation](https://git-scm.com/docs/git-worktree.html); [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/).
[^3]: PR #331 at commit `83e72df1b6d588d10c27136732e8d07647b39b33`; verified against `shared/scripts/work_cli.py`, `shared/scripts/work.py`, `shared/scripts/write_handoff_artifact.py`, `shared/scripts/handoff.py`, and `tests/shared/python/` on 2026-07-26.