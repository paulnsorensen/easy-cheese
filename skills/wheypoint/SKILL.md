---
name: wheypoint
description: Mark a checkpoint in the current conversation — compact it into a durable handoff document so a fresh agent can resume the work without context loss. Use when the user wants to preserve session state for a later or parallel session — phrases like "hand this off", "write a handoff", "drop a wheypoint", "checkpoint this", "compact the conversation", "I'm running low on context", "save where we are for the next session", "prep a handoff for another agent", "/wheypoint". Use even when the user just says "wrap up" or "I need to clear context" mid-task. Do NOT use for per-phase pipeline handoffs — those belong to `/cook`, `/press`, `/age`, and `/cure`.
license: MIT
---

# /wheypoint

`/wheypoint` captures just enough state for a cold reader to resume.

`/wheypoint` is for culture's end-of-session checkpoint and for the messy mid-task moment when no phase slug applies and context is about to be lost.

## Inputs

- The conversation so far (the primary input).
- Optional argument: a description of what the next session will focus on. When present, treat it as the lens and tailor the document to it. Drop state that does not serve that focus to a one-line pointer.
- Optional verb `--join <artifact-a> <artifact-b>`: join two exact committed handoff paths into the current WorkRecord. Never select either parent by slug or modification time.
- Optional verb `--split`: record two independent next moves as ordered `payload.tasks` directives in one wheypoint handoff.

```text
/wheypoint                       -> commit one resumable wheypoint artifact
/wheypoint --join <path> <path>  -> commit one artifact with both parents in provenance
/wheypoint --split               -> commit one artifact whose destination is tasks
```

## Flow

1. **Enter work.** Ensure a WorkRecord for a meaningful direct checkpoint or join the inherited work ID for a nested checkpoint.
2. **Inventory linked evidence.** Read the current WorkRecord, exact artifact paths, specs, PRs, issues, commits, and dirty state. Reference durable evidence instead of copying it.
3. **Write the document body** described under `## Document`, applying any focus argument as a compression lens.
4. **Redact** secrets on the way out (`## Redaction`).
5. **Commit and point at resumption.** Commit the `wheypoint` envelope and body through `handoff-commit`, print its returned path, and tell the user to resume with `/cheese --continue` from the original repository.

### `--join <artifact-a> <artifact-b>`

Load both exact versioned artifacts, verify their declared artifact paths, and record both paths under `provenance.parents`. Commit one new wheypoint artifact in the current WorkRecord. The body states only the combined goal, current state, and conflicts to reconcile; it references each parent instead of copying it.

### `--split`

Commit one wheypoint envelope with `next_phase: tasks`. `payload.tasks` is a non-empty ordered list of directives shaped exactly as `{phase, subject, input?}`. Each directive names a registered phase and a meaningful subject; `input` is a mapping. The resolver returns `action: tasks`, and the orchestrator owns any isolation or parallelism rather than encoding checkout commands in the handoff.

## Handoff contract

Wheypoint follows the shared executable [cross-skill work contract](../cheese/references/work-contract.md). It never hand-writes frontmatter or derives a flat notes path.

Commit `phase: wheypoint` with:

- `status: ok` when the recorded destination is unblocked.
- `status: halt` plus a non-empty `halt_reason` when a blocker or human decision must be resolved first. Use `next_phase: hold` for a decision gate; `handoff-resolve` returns `action: halt` and does not dispatch.
- `next_phase` chosen from the phase-owned declaration: `mold`, `cook`, `press`, `age`, `cure`, `affinage`, `briesearch`, `culture`, `done`, `hold`, or `tasks`.
- `payload: {}` except for `next_phase: tasks`, which requires `payload.tasks` in the directive shape above.
- `provenance` containing immutable capture data when available: session identity, branch and commit, UTC timestamp, exact parent artifact paths, and any inherited baseline evidence. Never accept user-supplied provenance as observed fact.
- An explicit `work_patch.scope`. Put resumable shared state, decisions, and open questions in the WorkRecord's working context; put the human-readable checkpoint under `## Document` in the committed body.

The runtime derives `.cheese/wheypoint/<work-id>/<operation-id>-<slug>.md`. Retry an interrupted commit with the exact same request and operation ID; changed content requires a new operation ID.

After commit, call `handoff-resolve`. `dispatch` invokes the returned phase with the inherited work ID; `halt`, `hold`, `tasks`, `unavailable`, and `done` follow the shared resolver semantics without inventing a command. Any user choice follows the shared [handoff gate](../cheese/references/handoff-gate.md). Treat inherited `payload.baseline` evidence as settled state per [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md): do not re-ask, re-flag, or re-halt identical failures.
## Document

Within the committed body, write a `## Document` section. Open with the answer; keep every claim readable to someone who has not seen the conversation. Cover, in order, only the parts that carry signal:

- **Goal.** The one or two sentences that say what we are trying to achieve.
- **State.** What is done and verified, what is in-flight, what is untouched. Be honest about partial work; a half-finished step described accurately beats a tidy lie (Rule 9).
- **Key decisions and constraints.** The choices a fresh agent would otherwise re-litigate, each with a calibrated tag (`` `<certain>` `` / `` `<speculating>` `` / `` `<don't know>` ``) and a one-line why.
- **Open questions and blockers.** What is unresolved and what it is waiting on.
- **Artifacts.** A list of paths and URLs, not their contents. See `## Do not duplicate`.
- **Suggested skills.** The concrete next moves. See `## Suggested skills` for the state-to-skill mapping.
- **Environment.** Branch, dirty files, anything non-obvious about the working state. Redacted.

Follow the house style in [`../cheese/references/formatting.md`](../cheese/references/formatting.md): no em-dashes, complete sentences in prose, no throat-clearing, calibrated tags on the claim.

## Suggested skills

Derive the envelope's `next_phase` and `status` from the body's blockers, not from optimism. Pick the single best next phase from the table; when two or more independent tracks remain, use `next_phase: tasks` and exact structured directives.

| Where the session is | Suggested move | `next_phase` |
| --- | --- | --- |
| Fuzzy idea, no approved spec yet | `/mold` | `mold` |
| Research wanted before deciding or building | `/briesearch <question>` | `briesearch` |
| Wants to think a problem through, no writes | `/culture` | `culture` |
| Next step blocked on a human decision | record the decision dossier | `hold` with `status: halt` |
| Compacting or stringing along, no action implied | restore orientation, wait | `hold` |
| Approved spec, not yet implemented | `/cook <spec-path>` | `cook` |
| Code written, not yet hardened or reviewed | `/press` | `press` |
| Implementation done, review wanted now | `/age` | `age` |
| Review findings in hand, fixes not applied | `/cure` | `cure` |
| PR has review comments or failing CI | `/affinage <pr>` | `affinage` |
| Work genuinely finished | record only | `done` |

When the session is interrupted mid-phase, resume that same registered phase with the inherited WorkRecord. A consequential decision gate requires a `## Decision dossier` in the body with options, evidence, tradeoffs, and prior leanings. `hold` and `done` need only enough orientation to distinguish paused from terminal work.

## Required body sections by state

| State | Required Document sections |
| --- | --- |
| `status: halt`, `next_phase: hold` | A `## Decision dossier` per open fork with options, evidence at `file:line`, what-each-breaks, and prior leanings. |
| `next_phase: culture` | The discussion agenda and open-thread state. |
| `next_phase: cure` | The exact findings artifact reference and locked selection, when present. |
| `next_phase: cook`, `press`, or `age` | The exact spec path and artifact pointers; never a reconstructed slug path. |
| `next_phase: hold` or `done` | Orientation only, enough to distinguish paused from terminal work. |
| `next_phase: tasks` | Shared orientation plus the ordered task directives in `payload.tasks`. |

The decision-dossier mandate overrides the "just enough state" compression rule for halted decision gates.

## Do not duplicate

The point of a handoff is to be short enough to read cold. Anything already captured in a durable artifact gets a reference, not a copy:

- Specs, findings reports, research reports under `.cheese/` — link by path.
- PRs, issues, commits, diffs — link by URL or sha.
- Plans, ADRs, design docs — link by path or URL.

Summarise an artifact only when the summary is genuinely shorter than its pointer. Re-pasting a diff or a spec into the handoff is the failure mode this skill exists to avoid.

## Redaction

Strip anything sensitive before writing: API keys, tokens, passwords, connection strings, and personally identifiable information. If a secret is required for the next session, reference where it lives (env var name, secret manager path), never its value.

## Handoff

The versioned wheypoint artifact is the only file this skill writes. No commits, PRs, or production-code edits. End by showing its orientation, a clickable link to the exact runtime-returned artifact path, and the repo-root-aware continuation command:

```bash
cd <absolute-repo-path>
/cheese --continue
```

## Work continuity

Follow the executable [cross-skill work contract](../cheese/references/work-contract.md) before phase work. A meaningful direct invocation ensures one WorkRecord; a nested invocation joins the inherited work ID. Emitting phases commit their versioned envelope and report body through `handoff-commit`, then act only on `handoff-resolve`. Never write or route from a legacy line-based handoff header.
