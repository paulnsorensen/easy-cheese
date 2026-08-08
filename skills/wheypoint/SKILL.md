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

## Flow

1. **Derive a slug** from the task (e.g. `auth-retry-backoff`). Reuse an existing slug if this session already owns one under `.cheese/`.
2. **Inventory what already exists.** List the `.cheese/` artifacts, specs, PRs, issues, commits, and diffs this session produced or touched. These get referenced, never re-summarised.
3. **Rehydrate.** `python3 skills/wheypoint/scripts/wheypoint.pyz show --work-id <id>` (bundle fallback: `${CLAUDE_SKILL_DIR}/scripts/wheypoint.pyz`) returns the record. Mandatory after a compaction: a compaction-marked delta is rejected unless the revision it declares as rehydrated is the current one.
4. **Build a semantic `WheypointDelta`**, not a rewritten document. `expected_revision_id` is the revision you rehydrated, or the genesis sentinel when this work has no record yet — that sentinel creates the first record, so there is no create step. Omitting a protected decision, question, blocker, or artifact link carries it forward; retiring one takes an explicit transition naming its entry ID, action, and rationale. A focus argument is the delta's lens.
5. **Commit through the runtime.** Pipe the delta as JSON to `wheypoint.pyz commit`. It assigns the revision, derives `status:`, and writes the immutable revision plus the Markdown `WheypointProjection` at `.cheese/notes/<slug>.md` — a generated projection, never the authority: never hand-edit it, never resume from it. A rejected commit is a real failure: fix the delta and re-commit, never hand-write the note.
6. **Redact** secrets on the way out (`## Redaction`).
7. **Report durability.** State the durability the commit result reports (`canonical-local`, `repo-snapshot`, or `published`); never run a Git commit, push, or publish to raise it. Point at resumption per `## Handoff`.

## Handoff slug

Prepend the standard resumable slug to the top of the file so `/cheese --continue` can route from it without reading the whole document:

```markdown
status: ok | gated: <one-line decision> | halt: <one-line reason>
next: mold | cut | cook | press | age | cure | affinage | briesearch | culture | hold | tasks | done
mode: single | parallel
artifact: <path-to-richer-report, or PR ref (PR#<n> / URL) when next: affinage, else none>
session: <harness>:<session-id>      # optional; auto-filled provenance
git: <branch>@<short-sha>            # optional; auto-filled provenance
created: <UTC ISO-8601>              # optional; auto-filled provenance
parents: [<slug>, ...]               # optional; lineage (join => 2+, split-child => 1)
baseline: none | <block — carries a recorded baseline block forward from an upstream cook/press/cure handoff; see ../cook/references/quality-gates.md>
<one-line orientation: where the session is and what is mid-flight>
```

`mode:` is optional for backwards compatibility; omitted mode means `mode: single`. In `mode: single`, `next:` names the skill the cold reader should run, which is the machine-readable form of the suggested-skills section below. Use `done` only when the work is genuinely finished and the handoff is a record, not a baton. `/cheese --continue <slug>` resolves the slug through `wheypoint.pyz resolve` and dispatches `next:` only from the validated current revision; an absolute note path resolves as an explicit path first. When `next: affinage`, record the PR reference (`PR#<n>` or its URL) in `artifact:` so the resume dispatches `/affinage <pr>` explicitly rather than relying on branch auto-detection.
Pipeline: `culture -> mold -> cut -> cook -> press -> age -> cure -> plate`. Mold `red-required` checkpoints use `next: cut`; Cut success uses `next: cook` with the authoritative GateReceipt in `artifact:`. Resume preserves `mode:`, `--hard`, `--open-pr`, `--safe`, and explicit `--auto`. Press corrective work remains `continue: press-corrective-cook`, not a global Press-to-Cook dispatch.

When the checkpointed session carries a recorded `baseline:` block, carry it into the delta unchanged: it is settled state, not something the resumed phase should re-ask about or re-halt on. See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md).

### Provenance fields

These optional fields precede the orientation line and come only from the live session; pre-provenance notes remain valid.

- **`session: <harness>:<session-id>`** — active Claude JSONL id, Codex rollout id, or OpenCode session row. Omit when unavailable; Claude's newest-mtime heuristic is `<speculative>`.
- **`git: <branch>@<short-sha>`** — branch and short commit from a callable, read-only git inspection capability (`git status --short --branch`; `git rev-parse --short HEAD`). Omit the field when git inspection is unavailable, outside git, or incomplete.
- **`created: <UTC ISO-8601>`** — UTC capture time.
- **`parents: [<slug>, ...]`** — lineage. Legacy `--join` writes `parents: [<slugA>, <slugB>]`; `--split` children write `parents: [<current-slug>]`. Both remain outside this continuity contract: they rewrite `.cheese/notes/` Markdown and commit no delta.

### `status:` values

Status is **derived** by the runtime, never asserted by the author: an active human-blocking question or blocker derives `gated:` and requires a decision dossier, and no caller can force `ok`.

- **`ok`** — the next step is unblocked; `/cheese --continue` auto-dispatches `next:`.
- **`gated: <one-line decision>`** — work is fine, but the next step is blocked on a human decision. Name the decision in one line. On `/cheese --continue`, the reader surfaces the decision plus the body's open-questions/blockers and asks which direction (research / decide / build); it dispatches nothing until the user picks. Never collapse a gate into a bare actionable `next:` with `status: ok` — that is the misfire this contract exists to stop. Any open blocker in the body mandates `status: gated:`, not `status: ok`.
- **`halt: <one-line reason>`** — legacy vocabulary, valid only in hand-written notes read through the legacy fallback, with unchanged semantics: surface the reason, then dispatch the runnable `next:`. The runtime never derives it and the derived set stays two-valued on purpose: `halt` records how the previous session ended, while derived status records whether continuation is blocked on a human, and a session can halt on an environment failure with nothing left to decide. That difference is deliberate, not a contradiction to close by adding `halt` to the derived set.

### `next:` values and semantics

Single-value `next:` is one of the pipeline phases (`mold | cut | cook | press | age | cure | affinage`), a read-only kickoff (`briesearch | culture`), `hold`, `tasks` (with `mode: parallel`), or `done`.

- **`mold` / `cut` / `cook` / `press` / `age` / `cure`** — the pipeline phases. Which one fits the session state (and the mid-phase resume case, e.g. `/cook` interrupted) is defined by the `## Suggested skills` mapping table below, which owns these semantics.
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
- The inline list is restricted to read-only skills (`briesearch | culture`). Parallel *write* efforts still require the heavyweight `mode: parallel` + `tasks:` block with worktree/branch isolation below; sequential *pipeline* chaining stays the job of `--auto` / `/cook`'s fan pathway.

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
    intent: cook
    repo: /Users/marcus/Documents/multiplier
    worktree: /Users/marcus/Documents/multiplier-01
    branch: marcus/kip-77-ai-test-server
    branch_from: origin/main
    command: /cook .cheese/specs/kip-77-ai-test-server.md
  - slug: kip-76-ai-service-spin-up
    intent: cook
    repo: /Users/marcus/Documents/multiplier
    worktree: /Users/marcus/Documents/multiplier-02
    branch: marcus/kip-76-ai-service-spin-up
    branch_from: origin/main
    command: /cook .cheese/specs/kip-76-ai-service-spin-up.md
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
| Approved `red-required` spec, not yet outer-tested | `/cut <spec-path>` | `cut` |
| Code written, not yet hardened or reviewed | `/press <slug>` then `/age` | `press` |
| Implementation done, review wanted now | `/age <ref>` | `age` |
| Review findings in hand, fixes not applied | `/cure <slug>` | `cure` |
| PR has review comments or failing CI | `/affinage <pr>` | `affinage` |
| Hard bug still un-diagnosed | surface the blocker; invoke `/pasteurize` once ready | — (set `status: gated:`) |
| Work genuinely finished | record only, no baton | `done` |

When the session sits mid-phase (e.g. `/cook` was interrupted), suggest re-entering that same phase with the slug. Tailor to the optional focus argument when the user gave one: it overrides the table if the next session is meant to do something other than advance the pipeline.

## Required body sections by state

The opening line ("`/wheypoint` captures just enough state for a cold reader to resume") sets the default: compress everything that does not serve the resume. This table names the one exception and pins the minimum `## Document` sections each `status:`/`next:` combination requires, so compression never eats the state a resume actually needs.

| state | required Document sections |
| --- | --- |
| `status: gated:` | `## Decision dossier` — per open fork: options / evidence `file:line` / what-each-breaks / prior leanings |
| `next: culture` | agenda + open-thread state |
| `next: cure` | findings artifact ref |
| `next: cook` / `press` / `age` | spec/slug pointers per existing conventions |
| `next: cut` | approved spec and GateReceipt handoff pointers |
| `next: hold` / `done` | orientation only |

**`status: gated:` overrides the "just enough state" compression rule for gated notes.** Every open fork gets its own `## Decision dossier` entry — options considered, evidence as `file:line` citations, what each option breaks, and any prior leaning from the session — instead of the one-line decision the compression default would otherwise leave. A resumed session with a consequential fork rebuilds its prose weighing from this dossier; see [`../cheese/references/ask-user-question.md`](../cheese/references/ask-user-question.md) § When to structure for why an undiscussed design fork needs that weighing rather than a structured confirm.

## Do not duplicate

The point of a handoff is to be short enough to read cold. Anything already captured in a durable artifact gets a reference, not a copy:

- Specs, findings reports, research reports under `.cheese/` — link by path.
- PRs, issues, commits, diffs — link by URL or sha.
- Plans, ADRs, design docs — link by path or URL.

Summarise an artifact only when the summary is genuinely shorter than its pointer. Re-pasting a diff or a spec into the handoff is the failure mode this skill exists to avoid.

## Redaction

Strip anything sensitive before writing: API keys, tokens, passwords, connection strings, and personally identifiable information. If a secret is required for the next session, reference where it lives (env var name, secret manager path), never its value.

## Handoff

`/wheypoint` writes only through `wheypoint.pyz commit`: the canonical record, its immutable revision, and the generated projection. No Git commits, pushes, PRs, or production-code edits — durability is reported, never automatically raised. Use the host's read-only inspection capabilities plus a write capability scoped to the durable corpus and `.cheese/notes/**`. The slug header keeps the shape `shared/scripts/handoff.py` parses and renders today; the continuity codec is additive, so `parse_handoff_slug()` and its callers are unchanged. End by showing the slug's orientation line, a normal Markdown link to the projection, and repo-root-aware resumption commands. Keep the note link outside fenced code so it is clickable. The link line should match this shape: `Wheypoint dropped: [.cheese/notes/<slug>.md](<absolute-note-path>)`.

Resume from the original repo with `/cheese --continue <slug>` after `cd <absolute-repo-path>`, or from anywhere with `/cheese --continue <absolute-repo-path>/.cheese/notes/<slug>.md`.
