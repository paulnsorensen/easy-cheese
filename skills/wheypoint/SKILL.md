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
- The optional argument shapes only the orientation line; the focus never removes a decision, question, blocker, or directive.

## Runtime commands

Run every command through this skill's archive by its resolved installed bundle path; see [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md).
When the consumer repository lacks `skills/`, resolve the installed bundle path before execution; never assume the easy-cheese checkout or current working directory.

```bash
python3 skills/wheypoint/scripts/wheypoint.pyz turns [--session <id> | --transcript <path>]
python3 skills/wheypoint/scripts/wheypoint.pyz show <work-id> [--project <key>]
python3 skills/wheypoint/scripts/wheypoint.pyz validate [intent.json]
python3 skills/wheypoint/scripts/wheypoint.pyz checkpoint [--compacted <proof.json>] [intent.json]
python3 skills/wheypoint/scripts/wheypoint.pyz checkpoint <work-id> --question "<q>" --gates --decision "<d>" --rationale "<why>" --directive "<d>" --quote "<words>" --link <ref> --kind <edge-kind>
python3 skills/wheypoint/scripts/wheypoint.pyz schema checkpoint-intent
python3 skills/wheypoint/scripts/wheypoint.pyz resolve <absolute-path | work-id | slug> [--project <key>] [--workspace-root <checkout>]
python3 skills/wheypoint/scripts/wheypoint.pyz lint <projection-path>
python3 skills/wheypoint/scripts/wheypoint.pyz list [--scope project | machine] [--grep <text>]... [--status <s>]... [--next <move>]... [--project <key>]... [--entry-kind <k>]... [--entry-state <s>]... [--gated | --no-gated] [--edge-kind <k>]... [--linked-to <ref>]... [--forked-from <work-id>]...
python3 skills/wheypoint/scripts/wheypoint.pyz log <work-id> [--project <key>]
python3 skills/wheypoint/scripts/wheypoint.pyz fork <parent> <child> --orientation "<child title>" [--move <id>]... [--copy <id>]... [--dossier <fork title>]... [--link <ref>]... [--next <move> [--artifact <a>]]
python3 skills/wheypoint/scripts/wheypoint.pyz link <work-id> <ref> --kind <edge-kind> [--covers <id>]... [--rationale "<why>"]
python3 skills/wheypoint/scripts/wheypoint.pyz unlink <work-id> <ref> --kind <edge-kind>
python3 skills/wheypoint/scripts/wheypoint.pyz shape [<work-id>] [--scope project | machine] [--depth <n>] [--kind <edge-kind>]...
python3 skills/wheypoint/scripts/wheypoint.pyz backlinks <ref> [--scope project | machine]
```

Repeat `--grep`, `--status`, `--next`, or `--project` to search several values in one `list` call; a hit matching any value of one flag is kept, and distinct flags combine with AND; never loop over `list` once per term.
`fork`, `link`, and `unlink` write only the named record; [`references/work-graph.md`](references/work-graph.md) gives refs, edge kinds, pending reconciliation, and the `list` graph filters.
The counterpart record reports `fork-pending` or `link-pending` until its next `checkpoint` applies the change.
`resolve`, `lint`, `list`, `log`, `show`, `shape`, `backlinks`, `schema`, and `turns` only read; direct invocations return output, and **STOP** before checkpoint writing.
`/cheese --continue` uses `resolve` and never invokes another archive; slash commands are host renderings, not the control model.
Foreign machine hits require the owning checkout; follow [the continuation protocol](../cheese/references/continue-resume.md).
The parent delegates persistence to this capability as one structured checkpoint task and runs `validate` before `checkpoint`; workers never invoke either command at a hard limit.
Phase skills resolve with their own `wheypoint-resolve --ref <slug>` command; follow [`references/delta-contract.md`](references/delta-contract.md) for its outcomes, `working_context`, and findings.

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
- It refuses `next: cook` without an `artifact`.
- It refuses text that matches a credential pattern and names the field.
- It refuses an empty `artifact_links` or `remove_artifact_links` list.
- It derives `status:` from the gating entries per the [handback contract](../cheese/references/handback-contract.md); no author sets it.
- It refuses a `baseline` key rather than drop it; a Cook baseline stays in the Cook handoff.
- It requires a dossier fork for each gating entry.
- It derives every identifier, digest, and revision.
- It refuses an agent-authored `fork` transition and a `forked_from` or `forked_to` edge in a delta.
- It refuses `notes` over 6000 characters.

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
The projection body shows gates, open entries, decisions, directives, notes, context, artifacts, the dossier, and tasks.
The projection is never the authority; never edit it and never resume from it by hand.

## `next:` values

The meaning of each `next:` value is in [`references/intent-contract.md`](references/intent-contract.md); `briesearch` and `culture` are read-only kickoffs, and `tasks` follows [`references/parallel-handoffs.md`](references/parallel-handoffs.md).
A missing `next:` makes the handoff malformed; use `hold` when no action follows.
Derive `next:` and `status:` from the open questions and blockers, not from expected success.

Use `status: gated:` for every human decision; the resumed agent asks through the shared [handoff gate](../cheese/references/handoff-gate.md) before it dispatches.

Handwritten notes, their legacy values, and their provenance fields are in [`references/legacy-notes.md`](references/legacy-notes.md) and [`references/provenance-fields.md`](references/provenance-fields.md).

## Rules

- Never run a Git commit, push, or publication to raise durability.
- Never write a note by hand, never edit a generated projection, and never include a secret value.
- Reference each artifact by path or URL; do not copy its contents.
- Use complete sentences; write one sentence per line.

## Handoff

End with the orientation and this link: `Wheypoint dropped: [.cheese/notes/<slug>.md](<absolute-note-path>)`.
