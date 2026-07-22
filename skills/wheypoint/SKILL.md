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
- Optional verb `--join <slugA> <slugB>`: merge two existing handoff notes into one. Reads both notes from `.cheese/notes/` and writes a single merged note whose `parents:` lists both slugs.
- Optional verb `--split`: fork the current thread into two resumable tracks. Writes two child notes, each with `parents: [<current-slug>]` and a distinct slug.

```text
/wheypoint                     -> one note with session/git/created auto-filled
/wheypoint --join A B          -> one merged note, parents: [A, B]
/wheypoint --split             -> two child notes, each parents: [<current>]
```

## Flow

1. **Derive a slug** from the task (e.g. `auth-retry-backoff`). Reuse an existing slug if this session already owns one under `.cheese/`.
2. **Inventory what already exists.** List the `.cheese/` artifacts, specs, PRs, issues, commits, and diffs this session produced or touched. These get referenced, never re-summarised.
3. **Write the handoff document** to `.cheese/notes/<slug>.md` with the slug header (`## Handoff slug`) and body (`## Document`) below. When a focus argument was given, apply it as the lens throughout: emphasise state and decisions that serve the focus, and compress everything else to a one-line pointer.
4. **Redact** secrets on the way out (`## Redaction`).
5. **Point at resumption.** End by telling the user how to resume with `/cheese --continue <slug>` from the original repo, and include an absolute clickable path to the handoff note so the user can find it from any working directory.

### `--join <slugA> <slugB>`

Merge two interrupted threads into one resumable note.

1. Read both source notes from `.cheese/notes/<slugA>.md` and `.cheese/notes/<slugB>.md`.
2. Derive a merged slug that names the joined effort.
3. Write ONE note to `.cheese/notes/<merged-slug>.md` with `parents: [<slugA>, <slugB>]` and the usual auto-filled provenance (`session:` / `git:` / `created:` from the live session).
4. In `## Document`, consolidate both sources' Goal / State / Key decisions by **reference**, not re-paste (per `## Do not duplicate`): point at each source note by path and capture only the merged picture and any conflicts to reconcile.
5. Point at resumption as in the default flow.

### `--split`

Fork the current thread into two parallel tracks.

1. Take the current thread's slug as the parent (derive it as in step 1 of the default flow).
2. Choose two distinct child slugs, one per track.
3. Write TWO notes, `.cheese/notes/<child-a>.md` and `.cheese/notes/<child-b>.md`, each with `parents: [<current-slug>]`, its own auto-filled provenance, and a `## Document` scoped to that track's slice of the work.
4. Point at resumption for each child so both tracks can be resumed independently.

## Handoff slug

Prepend the standard resumable slug to the top of the file so `/cheese --continue` can route from it without reading the whole document:

```markdown
status: ok | gated: <one-line decision> | halt: <one-line reason>
next: mold | cook | press | age | cure | affinage | briesearch | culture | hold | tasks | done
mode: single | parallel
artifact: <path-to-richer-report, or PR ref (PR#<n> / URL) when next: affinage, else none>
session: <harness>:<session-id>      # optional; auto-filled provenance
git: <branch>@<short-sha>            # optional; auto-filled provenance
created: <UTC ISO-8601>              # optional; auto-filled provenance
parents: [<slug>, ...]               # optional; lineage (join => 2+, split-child => 1)
baseline: <optional — carries a recorded baseline block forward from an upstream cook/press/cure handoff; see ../cook/references/quality-gates.md>
<one-line orientation: where the session is and what is mid-flight>
```

`mode:` is optional for backwards compatibility; omitted mode means `mode: single`. In `mode: single`, `next:` names the skill the cold reader should run, which is the machine-readable form of the suggested-skills section below. Use `done` only when the work is genuinely finished and the handoff is a record, not a baton. `/cheese --continue <slug>` scans `.cheese/notes/<slug>.md` and dispatches `next:` directly; `/cheese --continue <absolute-note-path>` reads that handoff file directly when the user is outside the original repo. When `next: affinage`, record the PR reference (`PR#<n>` or its URL) in `artifact:` so the resume dispatches `/affinage <pr>` explicitly rather than relying on branch auto-detection.

When the checkpointed session carries a recorded `baseline:` block, propagate it verbatim to the child note: it is settled state, not something the resumed phase should re-ask about or re-halt on. `--split` carries the block unchanged to each child note; `--join` merges the parents' baseline entries into their union — a settled-state merge that never re-opens a recorded entry. See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md).

### Provenance fields

Four optional provenance fields sit between `artifact:` and the orientation line. Auto-fill each one from the live session; never take a user-supplied value. All four are optional and additive: a note carrying none of them is valid, and every consumer treats a pre-provenance note (none of these keys) as valid. Placement rule: the orientation line stays the first non-key line, so it must follow whichever of these fields are present.

- **`session: <harness>:<session-id>`** — the current session's harness and id, read from the per-harness source map:
  - **claude** — the newest `*.jsonl` in the encoded-cwd projects dir (`~/.claude/projects/<encoded-cwd>/`); its basename (minus `.jsonl`) is the session id.
  - **codex** — the `payload.cwd` field in the rollout meta line of the active rollout log.
  - **opencode** — the matching row in the `session` table.
  - When the harness is unknown or no log is accessible, omit the field. `<speculative>` the newest-mtime claude heuristic can bind the wrong `*.jsonl` when several live sessions share one cwd; the field is optional so a wrong bind is hand-correctable.
- **`git: <branch>@<short-sha>`** — the branch and short commit at capture time. Use any callable, read-only git inspection capability the active harness exposes. CLI transports may run `git status --short --branch` for the branch and `git rev-parse --short HEAD` for the short SHA. Omit the field when git inspection is unavailable, outside a git repository, or either value cannot be determined.
- **`created: <UTC ISO-8601>`** — the capture timestamp in UTC ISO-8601 (e.g. `2026-07-09T14:32:00Z`).
- **`parents: [<slug>, ...]`** — lineage. Empty or absent for a fresh single-thread note. `--join` sets two or more source slugs; each `--split` child sets exactly the current slug.

### `status:` values

- **`ok`** — the next step is unblocked; `/cheese --continue` auto-dispatches `next:`.
- **`gated: <one-line decision>`** — work is fine, but the next step is blocked on a human decision. Name the decision in one line. On `/cheese --continue`, the reader surfaces the decision plus the body's open-questions/blockers and asks which direction (research / decide / build); it dispatches nothing until the user picks. Never collapse a gate into a bare actionable `next:` with `status: ok` — that is the misfire this contract exists to stop. Any open blocker in the body mandates `status: gated:`, not `status: ok`.
- **`halt: <one-line reason>`** — a blocker stopped the work mid-flight; surface the reason, then dispatch the runnable `next:` (unchanged).

### `next:` values and semantics

Single-value `next:` is one of the pipeline phases (`mold | cook | press | age | cure | affinage`), a read-only kickoff (`briesearch | culture`), `hold`, `tasks` (with `mode: parallel`), or `done`.

- **`mold` / `cook` / `press` / `age` / `cure`** — the pipeline phases. Which one fits the session state (and the mid-phase resume case, e.g. `/cook` interrupted) is defined by the `## Suggested skills` mapping table below, which owns these semantics.
- **`affinage`** — PR has review comments or failing CI. Record the PR reference in `artifact:` (`PR#<n>` or URL) so the resume dispatches `/affinage <pr>` explicitly.
- **`briesearch | culture`** — read-only, low-risk next moves. Under `status: ok`, `/cheese --continue` auto-dispatches them directly (frictionless research/think kickoff), deriving any dispatch argument (e.g. `briesearch`'s question) from the orientation line. A move that needs a human decision belongs in `status: gated:`.
- **`hold`** — restore orientation and wait for instruction; dispatch nothing. For compacting or stringing context along when no action is implied. Distinct from `done` (work finished, record only).
- **`done`** — work genuinely finished; handoff is a record, not a baton. Use only for true terminal completion.
- **A missing `next:` is a malformed handoff.** `/cheese --continue` flags it (`malformed handoff: next: required`) rather than guessing or defaulting. Declare intent explicitly — `hold` is the value for "no action."

### `next:` list form

To kick off several read-only follow-ups from one handoff, `next:` may be a list with a required `order:`:

```markdown
next: [briesearch "slug1", briesearch "slug2", culture "slug3"]
order: parallel | sequential
```

- Each item is `<skill> "<arg>"`. `order:` is **required** when `next:` is a list.
- `order: parallel` — `/cheese --continue` fans out concurrent read agents, one per item, in the same turn.
- `order: sequential` — items run in listed order.
- The inline list is restricted to read-only skills (`briesearch | culture`). Parallel *write* efforts still require the heavyweight `mode: parallel` + `tasks:` block with worktree/branch isolation below; sequential *pipeline* chaining stays the job of `--auto` / `/ultracook`.

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

Follow the house style in [`../cheese/references/formatting.md`](../cheese/references/formatting.md): no em-dashes, complete sentences in prose, no throat-clearing, calibrated tags on the claim.

## Suggested skills

Derive `next:` and `status:` from the body's blockers, not from optimism. See `### status: values` for the gate rule.

Pick the next move from where the session actually is, name it as an easy-cheese skill with its argument, and write the same target into the slug's `next:` field. Suggest the *single* best next step, plus the step after it when the path is obvious. When the session has two or more independent tracks that can proceed without sharing branch state, write `mode: parallel`, set `next: tasks`, and put each exact skill invocation under `tasks:` instead of collapsing them into one sequential next step. For several read-only follow-ups, use the inline `next:` list with `order:` instead. The map:

| Where the session is | Suggest | `next:` |
| --- | --- | --- |
| Fuzzy idea, no approved spec yet | `/mold` | `mold` |
| Research wanted before deciding or building | `/briesearch <question>` | `briesearch` |
| Wants to think a problem through, no writes | `/culture` | `culture` |
| Next step blocked on a human decision | surface the decision, ask direction | — (set `status: gated:`) |
| Compacting or stringing along, no action implied | restore orientation, wait | `hold` |
| Approved spec, not yet implemented | `/cook <spec-path>` | `cook` |
| Code written, not yet hardened or reviewed | `/press <slug>` then `/age` | `press` |
| Implementation done, review wanted now | `/age <ref>` | `age` |
| Review findings in hand, fixes not applied | `/cure <slug>` | `cure` |
| PR has review comments or failing CI | `/affinage <pr>` | `affinage` |
| Hard bug still un-diagnosed | surface the blocker; invoke `/pasteurize` once ready | — (set `status: gated:`) |
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

The handoff document is the only thing `/wheypoint` writes. No commits, PRs, or production-code edits. Use the host's read-only inspection capabilities plus a write capability scoped to `.cheese/notes/**`. End by showing the slug's orientation line, a normal Markdown link to the note, and repo-root-aware resumption commands. Keep the note link outside fenced code so it is clickable. The link line should match this shape: `Wheypoint dropped: [.cheese/notes/<slug>.md](<absolute-note-path>)`.

Resume from original repo:

```bash
cd <absolute-repo-path>
/cheese --continue <slug>
```

Resume from anywhere:

```bash
/cheese --continue <absolute-repo-path>/.cheese/notes/<slug>.md
```
