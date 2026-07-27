# ADR: Cross-skill handoffs use a versioned envelope and phase-owned contracts

Status: accepted (2026-07-26)
Spec: [Cross-skill work contract](../specs/cross-skill-work-contract.md)

## Context

The shared parser recognizes fewer shapes than skill documentation emits: optional values are single-line, duplicate keys are rejected, Pasteurize places custom fields before orientation, and Wheypoint carries a separate provenance schema.[^1] Writers can also accept a phase or slug that path resolution later rejects.[^2]

## Decision

Every persisted phase artifact uses JSON object frontmatter inside `---` fences with a shared `HandoffEnvelope` and Markdown body. The envelope carries contract version, work and attempt IDs, operation ID, phase, status, next outcome, current artifact path, payload, and provenance. `artifact` always identifies the loaded file; upstream evidence belongs in payload inputs or provenance.

Every globally addressable workflow phase owns a human-authored `skills/<phase>/references/handoff-contract.yaml`, declaring its payload through a bounded type vocabulary and its allowed outgoing transitions. Destination-only phases carry contracts even when their outgoing-transition set is empty. The build assembles declarations into one compiled registry and rejects duplicate phases, unknown destinations, malformed contracts, and unsupported constructs.

Global validity and local availability are separate. A globally valid handoff persists when its destination is unavailable in the current harness; the resolver reports unavailable and does not dispatch. Only globally invalid transitions block persistence.

Envelope status is `ok | halt`; `halt` requires a non-empty reason and does not implicitly change WorkRecord lifecycle. `done | hold | tasks` are globally known control outcomes, never phases. `done` completes the current attempt, `hold` pauses it, and `tasks` requires an ordered non-empty directive list.

`WorkPatch` is closed and limited to curated context. Work-scoped changes target shared sections; attempt-scoped changes require the envelope attempt ID and target attempt context. Artifact linkage and lifecycle are derived from the validated envelope so callers cannot contradict an outcome.

Attempt lifecycle, task lifecycle, and whole-work lifecycle are separate revision-checked operations. Clearing a blocked attempt is explicit. Tasks receive deterministic IDs, bind to a claiming attempt, and complete in the same idempotent transaction as that attempt's handoff. Completed and abandoned items are terminal except that explicit `reopen_work` creates a new attempt while preserving history.

Artifact identity is operation-scoped. Paths are `.cheese/<phase>/<work-id>/<operation-id>-<slug>.md`; allocating the operation ID before rendering makes retries idempotent while preventing repeated slugs or phases from overwriting evidence. Reusing an operation ID with changed request content is rejected.

## Consequences

Cross-skill boundaries become typed without freezing invocation syntax or full report bodies. Runtime persistence is deterministic JSON, while phase owners retain readable YAML declarations. Legacy artifacts require conservative structural migration with originals and provenance preserved.

[^1]: `shared/scripts/handoff.py:45-49,87-116`; `skills/cook/SKILL.md:224-231`; `skills/age/SKILL.md:191-203,248-260`; `skills/pasteurize/SKILL.md:160-176`; `adr/wheypoint-provenance-schema-001.md:31-38`.
[^2]: `shared/scripts/write_handoff_artifact.py:95-128`; `shared/scripts/paths.py:239-260`.