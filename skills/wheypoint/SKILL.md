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

Use it for culture sessions, for work without a phase slug, and for a phase's **Checkpoint & stop** option.
A phase checkpoint is a standalone, non-terminal Wheypoint record, not a terminal phase artifact.
Workers at a hard limit return observations; the parent, not the worker, runs checkpoint persistence.

## Inputs

- The conversation is the primary input.
- The optional argument shapes only the orientation line; the focus never removes a decision, question, or directive.

## Runtime commands

Run every command through this skill's archive by its resolved installed bundle path; see [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md).
When the consumer repository lacks `skills/`, resolve the installed bundle path before execution; never assume the easy-cheese checkout or current working directory.

```bash
python3 skills/wheypoint/scripts/wheypoint.pyz turns [--session <id> | --transcript <path>]
python3 skills/wheypoint/scripts/wheypoint.pyz show <work-id> [--project <key>]
python3 skills/wheypoint/scripts/wheypoint.pyz validate [intent.json] [--base <revision_id>]
python3 skills/wheypoint/scripts/wheypoint.pyz checkpoint [intent.json] [--base <revision_id>]
python3 skills/wheypoint/scripts/wheypoint.pyz checkpoint <work-id> [--base <revision_id>] --question "<q>" --gates --rationale "<why>" --decision "<d>" --directive "<d>" --quote "<words>" --link <ref> --kind <edge-kind> [--covers <id>]...
python3 skills/wheypoint/scripts/wheypoint.pyz schema checkpoint-intent
python3 skills/wheypoint/scripts/wheypoint.pyz resolve <absolute-path | work-id | slug> [--project <key>] [--workspace-root <checkout>]
python3 skills/wheypoint/scripts/wheypoint.pyz list [--scope project | machine] [--grep <text>]... [--status <s>]... [--next <move>]... [--project <key>]... [--entry-kind <k>]... [--entry-state <s>]... [--gated | --no-gated] [--edge-kind <k>]... [--linked-to <ref>]... [--forked-from <work-id>]...
python3 skills/wheypoint/scripts/wheypoint.pyz log <work-id> [--project <key>]
python3 skills/wheypoint/scripts/wheypoint.pyz fork <parent> <child> --orientation "<child title>" [--next <move> [--artifact <a>]]
python3 skills/wheypoint/scripts/wheypoint.pyz handoff render | parse | dispatch
```

Repeat `--grep`, `--status`, `--next`, or `--project` to search several values in one `list` call; a hit matching any value of one flag is kept, and distinct flags combine with AND; never loop over `list` once per term.
`fork` writes only a child genesis record with one `forked_from` edge; [`references/work-graph.md`](references/work-graph.md) gives refs, edge kinds, and the `list` graph filters.
Create a link with `checkpoint --link`; there is no separate link command.
`resolve` validates artifact links, grounded paths, Git objects, and coverage.
`resolve`, `list`, `log`, `show`, `schema`, and `turns` only read; direct invocations return output, and **STOP** before checkpoint writing.
`/cheese --continue` uses `resolve` and never invokes another archive; slash commands are host renderings, not the control model.
Foreign machine hits require the owning checkout; follow [the continuation protocol](../cheese/references/continue-resume.md).
The parent delegates persistence to this capability as one structured checkpoint task and runs `validate` before `checkpoint`; workers never invoke either command at a hard limit.
Phase skills resolve with their own `wheypoint-resolve --ref <slug>` command; follow [`references/delta-contract.md`](references/delta-contract.md) for its outcomes, `working_context`, and findings.

## Flow

1. **Read the user's words.** Run `turns` and keep every user turn in view.
2. Map each turn to an entry, or write one line that says why the turn is not captured.
3. **Rehydrate.** Run `show` or `resolve` for the work id and note its `revision_id`; a first checkpoint needs no base.
4. Every write to an existing record needs that `revision_id` as `--base` (or `base_revision_id`).
   After a compaction, read again before you write.
5. **Write the intent.** Follow [`references/intent-contract.md`](references/intent-contract.md).
6. Put each user-stated constraint or preference in a `directive` entry with its verbatim `quote`.
7. Put each choice in a `decision` entry with a `rationale`.
8. Put each open item in a `question` entry; give a blocking question a `rationale`.
9. Record a parked fork as a `question` with `--gates` and a `--rationale` that names the options and your prior leaning.
10. Put the report a cold reader needs in `notes`.
11. Put paths and URLs in `artifact_links` and `working_context`, not their contents.
12. **Validate.** Run `validate --base <revision_id>` and fix every named problem.
13. **Checkpoint.** Run `checkpoint --base <revision_id>`.
    A `base-revision-required` or `stale-parent` refusal means: read again, apply your change again, then write.
14. **Report.** State the durability the result reports and the resume commands.

## What the runtime enforces

The runtime refuses an intent instead of dropping data.

- It refuses an unknown key and names its path.
- It refuses a first checkpoint that carries no entry and no notes.
- It refuses `next: affinage` without a PR reference in `artifact`.
- It refuses `next: cook` without an `artifact`.
- It refuses text that matches a credential pattern and names the field.
- It refuses an empty `artifact_links` or `remove_artifact_links` list.
- It derives `status:` from the gating entries per the [handback contract](../cheese/references/handback-contract.md); no author sets it.
- It refuses a `baseline` key rather than drop it; a Cook baseline stays in the Cook handoff.
- It requires a rationale for each blocking question a delta adds.
- It derives every identifier, digest, and revision.
- It refuses an agent-authored `fork` transition and a `forked_from` edge in a delta.
- It refuses `notes` over 6000 characters.
- It warns with `stale-notes` when a decision changes and `notes` stay as they were, marks that drift at the top of `## Notes`, and lists a decision that `checkpoint --supersede <old> [--by <new>] --rationale <why>` replaced under `## Superseded`.

Fix a refused intent and run `checkpoint` again.

## Handoff slug

The `checkpoint` command writes the shared preamble at the top of the generated projection; every consumer reads it with `parse_handoff_slug()`.

```markdown
status: <canonical status field>
next: mold | cook | press | age | cure | affinage | briesearch | culture | hold | tasks | done
artifact: <path, or PR#<n> / URL when next is affinage, else empty>
<one-line orientation: where the session is and what is mid-flight>
```

For `next: tasks` the projection adds a `mode: parallel` keyed line after `artifact:`; the keyed block after the orientation holds the Wheypoint pins.
The projection body shows gates, open entries, decisions, directives, notes, context, artifacts, tasks, and a final `## Identifiers` section.
The projection title is `# Wheypoint handoff`.
The projection is never the authority; never edit it and never resume from it by hand.

## `next:` values

The meaning of each `next:` value is in [`references/intent-contract.md`](references/intent-contract.md); `briesearch` and `culture` are read-only kickoffs, and `tasks` follows [`references/parallel-handoffs.md`](references/parallel-handoffs.md).
A missing `next:` makes the handoff malformed; use `hold` when no action follows.
Derive `next:` and `status:` from the open questions, not from expected success.

Use `status: gated:` for every human decision; the resumed agent asks through the shared [handoff gate](../cheese/references/handoff-gate.md) before it dispatches.

Handwritten notes, their legacy values, and their provenance fields are in [`references/legacy-notes.md`](references/legacy-notes.md) and [`references/provenance-fields.md`](references/provenance-fields.md).

## Rules

- Never run a Git commit, push, or publication to raise durability.
- Never write a note by hand, never edit a generated projection, and never include a secret value.
- Reference each artifact by path or URL; do not copy its contents.
- Use complete sentences; write one sentence per line.

## Handoff

End with the orientation and this link: `Wheypoint dropped: [.cheese/notes/<slug>.md](<absolute-note-path>)`.
