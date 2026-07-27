# Easy-cheese domain model

The workflow-continuity model distinguishes a user's durable work item from branch/worktree executions, queued phase directives, and evidence passed between phases. The approved contract is [Cross-skill work contract](./specs/cross-skill-work-contract.md).

## Workflow continuity

**WorkRecord** — persisted continuity record for one user work item across conversations, phases, branches, and worktrees.
_Avoid_: session, latest note
_Code_: `shared/scripts/work.py`

**WorkAttempt** — one branch/worktree execution belonging to a WorkRecord; it owns tentative execution context, phase progress, and artifact links.
_Avoid_: session, Hard Cheese attempt
_Code_: `shared/scripts/work.py`

**WorkTask** — ordered phase directive created by `next: tasks`; it has deterministic identity, binds to a claiming WorkAttempt, and remains nonterminal until completed or explicitly abandoned.
_Avoid_: phase name, background session
_Code_: `shared/scripts/work.py`

**AttemptStatePatch** — revision-checked explicit lifecycle transition for a WorkAttempt, distinct from curated context edits.
_Avoid_: implicit unblock, status field edit
_Code_: `shared/scripts/work.py`

**WorktreeKey** — local identity derived from a Git worktree-specific Git directory; it groups active or paused WorkAttempts for deterministic continuation.
_Avoid_: branch key, cwd key
_Code_: `shared/scripts/paths.py`

**HandoffEnvelope** — versioned, schema-bounded YAML frontmatter surrounding a phase-owned Markdown report.
_Avoid_: positional status header, unrestricted YAML document
_Code_: `shared/scripts/handoff.py`

**PhaseContract** — a human-authored YAML declaration of a source phase's payload schema and permitted outgoing transitions; it is compiled into the Cheese runtime registry.
_Avoid_: universal payload schema, unpinned ambient YAML dependency
_Code_: `skills/<phase>/references/handoff-contract.yaml`

**Global transition registry** — build-assembled validation model containing every globally addressable workflow phase, destination-only contracts, and reserved control outcomes, independent of current harness installation.
_Avoid_: local availability list
_Code_: compiled into `skills/cheese/scripts/cheese.pyz`

**Repo-local work snapshot** — optional portable copy of a WorkRecord under `.cheese/work/`; imported or exported explicitly and never a second authority.
_Avoid_: automatic mirror, co-authoritative record
_Code_: `shared/scripts/work.py`