# ADR: Shared harness portability reference

The Codex/OMP portability cleanup should add one shared harness-portability reference and keep per-skill edits short.

## Context

A read-only audit found that multiple workflow skills still present Claude Code mechanisms as mandatory execution paths: `${CLAUDE_SKILL_DIR}/scripts/*.pyz`, Claude `Agent()` wording, `gh` CLI operations, and slash-command handoffs. The earlier harness-native overlap work already made `cheez-*` backend-flexible, so this decision covers the remaining workflow and orchestration docs.

## Decision

Use a shared-reference-first documentation contract. The reference should define semantic host capabilities for helper resolution, code tools, sub-agent dispatch, GitHub operations, and phase handoffs. Affected skills should link to that reference and keep only their local executable examples.

## Rationale

Inline mappings in every skill would duplicate the same OMP/Claude host vocabulary across many files and make later harness additions inconsistent. A shared reference keeps the portability contract in one place while preserving host-specific examples where they help execution.

## Consequences

- Implementation must add regression coverage that edited skills link to the shared reference and do not introduce conflicting portability vocabulary.
- Claude Code examples should remain where they are correct, but they must be labelled as host-specific examples rather than mandatory mechanisms.
- Helper-path wording must stay tied to repo-local or bundled helpers instead of inventing new path semantics.

## Source

Spec: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/codex-omp-portability.md`.
