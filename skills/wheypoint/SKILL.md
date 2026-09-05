---
name: wheypoint
description: >-
  Mark the current conversation as a durable handoff so a new agent can resume
  the work. Use when the user wants to preserve state for a later or parallel
  session. Triggers include "hand this off", "write a handoff", "drop a
  wheypoint", "checkpoint this", "compact the conversation", and
  "/wheypoint". Also use for "wrap up" or "I need to clear context" during a
  task. Do NOT use for phase handoffs from `/cook`, `/press`, `/age`, or
  `/cure`.
license: MIT
---

# /wheypoint

`/wheypoint` records the state a new agent needs to resume the work.

Use it for culture sessions, for work without a phase slug, and when a phase offers **Checkpoint & stop**.

## Inputs

- The conversation is the primary input.
- The optional argument names the next session's focus.
- The focus shapes the orientation line only.
- The focus never removes a decision, question, blocker, or directive.

## Runtime commands

Run every command through this skill's archive by its repository path; see [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md).

```bash
python3 skills/wheypoint/scripts/wheypoint.pyz turns [--session <id> | --transcript <path>]
python3 skills/wheypoint/scripts/wheypoint.pyz show --work-id <id>
python3 skills/wheypoint/scripts/wheypoint.pyz validate < intent.json
python3 skills/wheypoint/scripts/wheypoint.pyz checkpoint [--compacted <proof.json>] < intent.json
python3 skills/wheypoint/scripts/wheypoint.pyz schema checkpoint-intent
python3 skills/wheypoint/scripts/wheypoint.pyz resolve --ref <absolute-path | work-id | slug>
python3 skills/wheypoint/scripts/wheypoint.pyz lint <projection-path>
python3 skills/wheypoint/scripts/wheypoint.pyz list
python3 skills/wheypoint/scripts/wheypoint.pyz log --work-id <id>
```

`resolve`, `lint`, `list`, `log`, `show`, `schema`, and `turns` only read; direct invocations return output, and **STOP** before checkpoint writing.

`/cheese --continue` uses `resolve` and never invokes another archive; slash commands are host renderings, not the control model.

See [`references/commands.md`](references/commands.md) for the generated command list.

## Flow

1. **Read the user's words.** Run `turns` and keep every user turn in view.
2. Map each turn to an entry, or write one line that says why the turn is not captured.
3. **Rehydrate.** Run `show` for the work id; a first checkpoint binds the genesis sentinel itself.
4. After a compaction, rehydrate first and pass a proof with `--compacted`.
5. **Write the intent.** Follow [`references/intent-contract.md`](references/intent-contract.md).
6. Put each user-stated constraint or preference in a `directive` entry with its verbatim `quote`.
7. Put each choice in a `decision` entry with a `rationale`.
8. Put each open item in a `question` or `blocker` entry.
9. Record a parked fork in `decision_dossier` with its options, evidence, and prior leaning.
10. Put the report a cold reader needs in `notes`.
11. Put paths and URLs in `artifact_links` and `working_context`, not their contents.
12. **Validate.** Run `validate` and fix every named problem.
13. **Checkpoint.** Run `checkpoint`.
14. **Report.** State the durability the result reports and the resume commands.

## What the runtime enforces

The runtime refuses an intent instead of dropping data.

- It refuses an unknown key and names its path.
- It refuses a first checkpoint that carries no entry and no notes.
- It refuses `next: affinage` without a PR reference in `artifact`.
- It refuses `next: cook` or `next: cut` without an `artifact`.
- It refuses text that matches a credential pattern and names the field.
- It refuses an empty `artifact_links` or `remove_artifact_links` list.
- It derives `status:` from the gating entries per the [handback contract](../cheese/references/handback-contract.md); no author sets it.
- It refuses a `baseline` key rather than drop it; a Cook baseline stays in the Cook handoff.
- It requires a dossier fork for each gating entry.
- It derives every identifier, digest, and revision.

Fix a refused intent and run `checkpoint` again.

## Handoff slug

The `checkpoint` command writes the shared preamble at the top of the generated projection; every consumer reads it with `parse_handoff_slug()`.

```markdown
status: <canonical status field>
next: mold | cut | cook | press | age | cure | affinage | briesearch | culture | hold | tasks | done
artifact: <path, or PR#<n> / URL when next is affinage, else empty>
<one-line orientation: where the session is and what is mid-flight>
```

For `next: tasks` the projection adds a `mode: parallel` keyed line after `artifact:`; the keyed block after the orientation holds the Wheypoint pins.

The projection body shows gates, open entries, decisions, directives, notes, context, artifacts, the dossier, and tasks.

The projection is never the authority; never edit it and never resume from it by hand.

## `next:` values

- `mold`, `cut`, `cook`, `press`, `age`, `cure`: the next pipeline phase.
- `affinage`: PR review comments or failing CI; `artifact` names the PR.
- `briesearch`, `culture`: a read-only next move that `/cheese --continue` dispatches.
- `tasks`: independent moves; see [`references/parallel-handoffs.md`](references/parallel-handoffs.md).
- `hold`: restore orientation and wait for instructions.
- `done`: the work is complete; the checkpoint is a record, not a baton.
- A missing `next:` makes the handoff malformed; use `hold` when no action follows.

Derive `next:` and `status:` from the open questions and blockers, not from expected success.

Use `status: gated:` for every human decision; the resumed agent asks through the shared [handoff gate](../cheese/references/handoff-gate.md) before it dispatches.

Handwritten notes, their legacy values, and their provenance fields are in [`references/legacy-notes.md`](references/legacy-notes.md) and [`references/provenance-fields.md`](references/provenance-fields.md).

## Rules

- Never run a Git commit, push, or publication to raise durability.
- Never write a note by hand, never edit a generated projection, and never include a secret value.
- Reference each artifact by path or URL; do not copy its contents.
- Use complete sentences; write one sentence per line.

## Handoff

End with the orientation line, a Markdown link to the projection, and the resume commands.

Use this link form: `Wheypoint dropped: [.cheese/notes/<slug>.md](<absolute-note-path>)`.

From the repository run `/cheese --continue <slug>`; from elsewhere run `/cheese --continue <absolute-repo-path>/.cheese/notes/<slug>.md`.
