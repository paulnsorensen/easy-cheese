---
name: wheypoint
description: Mark a checkpoint in the current conversation — compact it into a durable handoff document so a fresh agent can resume the work without context loss. Use when the user wants to preserve session state for a later or parallel session — phrases like "hand this off", "write a handoff", "drop a wheypoint", "checkpoint this", "compact the conversation", "I'm running low on context", "save where we are for the next session", "prep a handoff for another agent", "/wheypoint". Writes `.cheese/notes/<slug>.md` with a resumable handoff slug, a state-mapped suggested-skills section, and redacted secrets, then points the user at `/cheese --continue <slug>`. Use even when the user just says "wrap up" or "I need to clear context" mid-task. Do NOT use for design-only no-write reasoning notes (`/culture`) or for per-phase pipeline handoffs — `/cook`, `/press`, `/age`, `/cure` already write their own slugs. Before `/cheese --continue`.
license: MIT
---

# /wheypoint

A wheypoint is a waypoint on the cheese's journey: a marked spot you can navigate back to. Use this skill when the conversation holds work-in-progress that a different agent (or a future you, in a fresh context) needs to continue. `/wheypoint` captures just enough state for a cold reader to resume, and nothing they could already read elsewhere.

Do not use it for no-write design dialogue (`/culture`) or as a substitute for a phase skill's own handoff slug. `/cook`, `/press`, `/age`, and `/cure` write their slugs at clean phase boundaries; `/wheypoint` is for the messy mid-task moment when none of those apply and context is about to be lost.

## Inputs

- The conversation so far. That is the primary input.
- Optional argument: a description of what the next session will focus on. When present, treat it as the lens and tailor the document to it. Drop state that does not serve that focus to a one-line pointer.

## Flow

1. **Derive a slug** from the task (e.g. `auth-retry-backoff`). Reuse an existing slug if this session already owns one under `.cheese/`.
2. **Inventory what already exists.** List the `.cheese/` artifacts, specs, PRs, issues, commits, and diffs this session produced or touched. These get referenced, never re-summarised.
3. **Write the handoff document** to `.cheese/notes/<slug>.md` with the slug header (`## Handoff slug`) and body (`## Document`) below.
4. **Redact** secrets on the way out (`## Redaction`).
5. **Point at resumption.** End by telling the user how to resume with `/cheese --continue <slug>` from the original repo, and include an absolute clickable path to the handoff note so the user can find it from any working directory.

## Handoff slug

Prepend the standard resumable slug to the top of the file so `/cheese --continue` can route from it without reading the whole document:

```markdown
status: ok | halt: <one-line reason>
next: mold | cook | press | age | cure | affinage | tasks | done
mode: single | parallel
artifact: <path-to-richer-report, or PR ref (PR#<n> / URL) when next: affinage, else none>
<one-line orientation: where the session is and what is mid-flight>
```

`mode:` is optional for backwards compatibility; omitted mode means `mode: single`. In `mode: single`, `next:` names the skill the cold reader should run, which is the machine-readable form of the suggested-skills section below. Use `done` only when the work is genuinely finished and the handoff is a record, not a baton. `/cheese --continue <slug>` scans `.cheese/notes/<slug>.md` and dispatches `next:` directly; `/cheese --continue <absolute-note-path>` reads that handoff file directly when the user is outside the original repo. When `next: affinage`, record the PR reference (`PR#<n>` or its URL) in `artifact:` so the resume dispatches `/affinage <pr>` explicitly rather than relying on branch auto-detection.

For multiple independent next moves, use `mode: parallel`, set `next: tasks`, add a `parallel:` block, and add a `tasks:` list immediately after the orientation line. Each task must carry its exact `command:`; commands may name different skills. Parallel write tasks must never share a checkout. Choose one portable isolation strategy:

| `worktree_strategy` | Use when | Required fields |
| --- | --- | --- |
| `existing` | The user already has durable bench checkouts | each write task has distinct `worktree:`, `branch:`, and `branch_from` |
| `create` | No checkouts exist yet | `worktree_root`, plus each write task has `branch:` and `branch_from` |
| `harness` | The host can create isolated threads/worktrees | each write task has `branch:` and `branch_from`; the host owns checkout creation |

Example:

```markdown
status: ok
next: tasks
mode: parallel
artifact: none
KIP-76 and KIP-77 are ready to run as independent PR efforts.
parallel:
  isolation: git-worktree
  worktree_strategy: existing
tasks:
  - slug: kip-77-ai-test-server
    intent: ultracook
    repo: /Users/marcus/Documents/multiplier
    worktree: /Users/marcus/Documents/multiplier-01
    branch: marcus/kip-77-ai-test-server
    branch_from: origin/main
    command: /ultracook .cheese/specs/kip-77-ai-test-server.md
  - slug: kip-76-ai-service-spin-up
    intent: ultracook
    repo: /Users/marcus/Documents/multiplier
    worktree: /Users/marcus/Documents/multiplier-02
    branch: marcus/kip-76-ai-service-spin-up
    branch_from: origin/main
    command: /ultracook .cheese/specs/kip-76-ai-service-spin-up.md
```

For a generic setup without existing benches, use `worktree_strategy: create` and add `worktree_root: ../.cheese-worktrees`; `/cheese --continue` derives one checkout per task from the task slug.

## Document

After the slug, write a `## Document` section. Open with the answer; keep every claim readable to someone who has not seen the conversation. Cover, in order, only the parts that carry signal:

- **Goal.** The one or two sentences that say what we are trying to achieve.
- **State.** What is done and verified, what is in-flight, what is untouched. Be honest about partial work; a half-finished step described accurately beats a tidy lie (Rule 9).
- **Key decisions and constraints.** The choices a fresh agent would otherwise re-litigate, each with a calibrated tag (`` `<certain>` `` / `` `<speculating>` `` / `` `<don't know>` ``) and a one-line why.
- **Open questions and blockers.** What is unresolved and what it is waiting on.
- **Artifacts.** A list of paths and URLs, not their contents. See `## Do not duplicate`.
- **Suggested skills.** The concrete next moves. See `## Suggested skills` for the state-to-skill mapping.
- **Environment.** Branch, dirty files, anything non-obvious about the working state. Redacted.

Follow the house style in [`../../shared/formatting.md`](../../shared/formatting.md): no em-dashes, complete sentences in prose, no throat-clearing, calibrated tags on the claim.

## Suggested skills

Pick the next move from where the session actually is, name it as an easy-cheese skill with its argument, and write the same target into the slug's `next:` field. Suggest the *single* best next step, plus the step after it when the path is obvious. When the session has two or more independent tracks that can proceed without sharing branch state, write `mode: parallel`, set `next: tasks`, and put each exact skill invocation under `tasks:` instead of collapsing them into one sequential next step. The map:

| Where the session is | Suggest | `next:` |
| --- | --- | --- |
| Fuzzy idea, no approved spec yet | `/mold` | `mold` |
| Approved spec, not yet implemented | `/cook <spec-path>` | `cook` |
| Code written, not yet hardened or reviewed | `/press <slug>` then `/age` | `press` |
| Implementation done, review wanted now | `/age <ref>` | `age` |
| Review findings in hand, fixes not applied | `/cure <slug>` | `cure` |
| PR has review comments or failing CI | `/affinage <pr>` | `affinage` |
| Hard bug still un-diagnosed | `/pasteurize <input>` | `cook` |
| Work genuinely finished | record only, no baton | `done` |

When the session sits mid-phase (e.g. `/cook` was interrupted), suggest re-entering that same phase with the slug. Tailor to the optional focus argument when the user gave one: it overrides the table if the next session is meant to do something other than advance the pipeline.

## Do not duplicate

The point of a handoff is to be short enough to read cold. Anything already captured in a durable artifact gets a reference, not a copy:

- Specs, findings reports, research reports under `.cheese/` — link by path.
- PRs, issues, commits, diffs — link by URL or sha.
- Plans, ADRs, design docs — link by path or URL.

Summarise an artifact only when the summary is genuinely shorter than its pointer. Re-pasting a diff or a spec into the handoff is the failure mode this skill exists to avoid.

## Redaction

Strip anything sensitive before writing: API keys, tokens, passwords, connection strings, and personally identifiable information. If a secret is required for the next session, reference where it lives (env var name, secret manager path), never its value.

## Handoff

The handoff document is the only thing `/wheypoint` writes. No commits, no PRs, no production-code edits. End by surfacing the slug's orientation line, a normal Markdown link to the note, and repo-root-aware resumption commands. Keep the note link outside fenced code so it is clickable. The link line should match this shape: `Wheypoint dropped: [.cheese/notes/<slug>.md](<absolute-note-path>)`.

Resume from original repo:

```bash
cd <absolute-repo-path>
/cheese --continue <slug>
```

Resume from anywhere:

```bash
/cheese --continue <absolute-repo-path>/.cheese/notes/<slug>.md
```
