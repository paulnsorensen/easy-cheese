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

`/wheypoint` captures just enough state for a new agent to resume.

Use `/wheypoint` for culture sessions or work without a phase slug.

`/wheypoint` does not replace a routine phase handoff from `/cook`, `/press`,
`/age`, or `/cure`.

Use it when the user selects **Checkpoint & stop** at one of those phases.

## Inputs

- Use the conversation as the primary input.
- The optional argument states the next session's focus.
- Use this argument as the document lens.
- Reduce unrelated state to a one-line reference.

## Flow

### Runtime commands

The `resolve` and `lint` commands only read state.

Run them through this skill's archive:

```bash
python3 skills/wheypoint/scripts/wheypoint.pyz resolve --ref <absolute-path | work-id | slug>
python3 skills/wheypoint/scripts/wheypoint.pyz lint <projection-path>
```

Direct invocations run, return output, and **STOP** before checkpoint writing.

`/cheese --continue` uses these terminal operations.

Never invoke another archive.

Slash commands are host renderings, not the control model.

Run the bundled archive by its repository path on every host. See [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md).

1. **Derive a slug.** Use a value such as `auth-retry-backoff`.
2. Reuse an existing slug when this session already owns it under `.cheese/`.
3. **List existing artifacts.** Include each artifact, spec, PR, issue, commit, and diff that this session touched.
4. Reference existing items. Do not summarize them again.
5. **Rehydrate the record.** Run `python3 skills/wheypoint/scripts/wheypoint.pyz show --work-id <id>`.
6. Rehydrate after compaction. The runtime rejects a compaction proof that does not name the current revision.
7. **State each change.** Specify the orientation, `next`, artifact, new entries, and transitions.
8. Give a reason for each transition. Omitted data carries forward.
9. Use the focus argument as the lens.
10. Follow [`references/delta-contract.md`](references/delta-contract.md) for all fields and rules.
11. **Create the checkpoint.** Pipe intent JSON to `python3 skills/wheypoint/scripts/wheypoint.pyz checkpoint`.
12. The command binds the rehydrated revision as the parent.
13. The command uses the genesis sentinel when no record exists.
14. Set `base_revision_id` when the command must reject a changed base.
15. The command assigns the revision and derives `status:`.
16. It writes an immutable revision and a generated projection at `.cheese/notes/<slug>.md`.
17. The projection is not the authority.
18. Never edit the projection or resume from it.
19. Fix a refused intent and run the command again.
20. Never write the note manually.
21. Use `python3 skills/wheypoint/scripts/wheypoint.pyz commit` only for a raw delta with an explicit `expected_revision_id`.
22. Use this command for a compaction proof.
23. **Remove secrets.** Follow `## Redaction`.
24. **Report durability.** State the result: `canonical-local`, `repo-snapshot`, or `published`.
25. Never run a Git commit, push, or publish to increase durability.
26. Give the resume commands from `## Handoff`.

## Handoff slug

The `checkpoint` command writes the slug at the start of the generated projection.

This slug lets `/cheese --continue` route without reading the complete document.

The first four lines are the shared handoff preamble.

Every consumer reads them with `parse_handoff_slug()`.

```markdown
status: <canonical status field>
next: mold | cut | cook | press | age | cure | affinage | briesearch | culture | hold | tasks | done
artifact: <path-to-richer-report, or PR ref (PR#<n> / URL) when next: affinage, else none>
<one-line orientation: where the session is and what is mid-flight>

work_id: <work id>
revision_id: <revision id>
record_digest: <sha256 of the record>
projection_digest: <sha256 of this document>
durability: canonical-local | repo-snapshot | published
schema_version: <integer>
```

The keyed block after the orientation holds the Wheypoint pins.

The runtime derives every line. Never write or edit this document by hand.

### Handwritten legacy notes

The `resolve` command also reads a handwritten note under `.cheese/notes/`.

That older format accepts `mode:`, `session:`, `git:`, `created:`, `parents:`,
and `baseline:` between `artifact:` and the orientation.

A legacy result is never authoritative. It gates a resume for a human decision.

The `checkpoint` command refuses each of those keys in an intent.

The record has no field for that data, so accepting the key would drop it.

`mode:` is optional in a legacy note.

An omitted mode means `mode: single`.

In `mode: single`, `next:` names the skill that the new agent runs.

This value also represents the suggested skill.

Use `done` only when the work is complete.

`/cheese --continue <slug>` resolves the slug through the `resolve` command.

It dispatches `next:` only from the validated current revision.

An absolute note path resolves as an explicit path first.

When `next: affinage`, put the PR reference in `artifact:`.

Use `PR#<n>` or the PR URL.

This value makes the runtime dispatch `/affinage <pr>` without branch detection.

Pipeline: `culture -> mold -> cook -> press -> age -> cure -> plate`.

Mold `red-required` checkpoints use `next: cook`.

Put the durable spec path in `artifact:`.

Resume preserves `mode:`, `--hard`, `--open-pr`, `--safe`, and explicit `--auto`.

Press corrective work remains `continue: press-corrective-cook`, not a global Press-to-Cook dispatch.

A handwritten legacy note can record a one-line `baseline:` value.

The baseline is settled state.

Do not re-ask, re-flag, or re-halt on identical baseline entries.

The canonical record carries no baseline field today.

The `checkpoint` command refuses a `baseline` key rather than drop it.

Keep a Cook baseline mapping in the Cook handoff until the record gains a
typed baseline field.

See [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md).

See [`references/provenance-fields.md`](references/provenance-fields.md) for provenance fields and legacy lineage commands.

### `status:` values

The [handback contract](../cheese/references/handback-contract.md) defines the `status:` grammar.

The rules below define Wheypoint status.

The runtime derives status.

The author does not set status.

An active question or blocker derives `gated:` and requires a decision dossier.

No caller can force `ok`.

- **`ok`**: The next step is not blocked. `/cheese --continue` dispatches `next:`.
- **`gated: <one-line decision>`**: A human decision blocks the next step.
- For `gated:`, state the decision on one line.
- The new agent shows the decision and the open entries.
- The new agent asks whether to research, decide, or build.
- It dispatches nothing until the user selects a direction.
- The new agent asks through the shared [handoff gate](../cheese/references/handoff-gate.md).
- Every open blocker requires `status: gated:`.
- Never replace a gate with `status: ok` and an actionable `next:`.
- **`halt: <one-line reason>`**: This legacy value is valid only in handwritten notes.
- The `resolve` command gates every legacy status whose disposition is not `proceed`.
- A legacy `halt` therefore stops. It shows the reason and dispatches nothing.
- The runtime never derives `halt`.
- Derived status has only `ok` and `gated:`.
- A session can halt after an environment failure without a human decision.

### `next:` values and semantics

A single `next:` value selects one move.

It accepts `mold`, `cut`, `cook`, `press`, `age`, `cure`, `affinage`, `briesearch`, `culture`, `hold`, `tasks`, or `done`.

- **`mold` / `cut` / `cook` / `press` / `age` / `cure`**: Select a pipeline phase.
- **`cut`**: Select the protected red evidence step before Cook changes production.
- Put the approved behavior spec path in `artifact:`.
- The `## Suggested skills` table defines which phase matches each state.
- **`affinage`**: Select this move for PR review comments or failing CI.
- Put `PR#<n>` or the PR URL in `artifact:`.
- **`briesearch | culture`**: Select a read-only next move.
- With `status: ok`, `/cheese --continue` dispatches the move.
- The runtime derives its argument from the orientation line.
- A move that requires a human decision uses `status: gated:`.
- **`hold`**: Restore orientation and wait for instructions.
- Use `hold` when no action follows the checkpoint.
- **`done`**: Record completed work without a handoff.
- Use `done` only for terminal completion.
- A missing `next:` makes the handoff malformed.
- `/cheese --continue` reports `malformed handoff: next: required`.
- Use `hold` when no action must start.

See [`references/parallel-handoffs.md`](references/parallel-handoffs.md) for multiple moves.

## Document

After the slug, write a `## Document` section.

Start with the answer.

Write for an agent that has not read the conversation.

Include only information that supports the resume.

Use this order:

- **Goal.** State the result that the work must achieve.
- **State.** State completed, verified, active, and untouched work.
- Describe partial work accurately.
- **Key decisions and constraints.** State each choice that a new agent could question again.
- Add one confidence tag: `` `<certain>` ``, `` `<speculating>` ``, or `` `<don't know>` ``.
- Give one short reason for each choice.
- **Open questions and blockers.** State each unresolved item and its dependency.
- **Artifacts.** List paths and URLs. Do not copy their contents.
- **Suggested skills.** State the exact next moves.
- **Environment.** State the branch, modified files, and unusual worktree state.
- Remove sensitive values from environment details.

Follow [`../cheese/references/formatting.md`](../cheese/references/formatting.md).

Apply the shared voice rules from [`../age/references/voice.md`](../age/references/voice.md).

Use complete sentences in prose.

Do not use em dashes or introductory filler.

Add a confidence tag to each claim.

## Suggested skills

Derive `next:` and `status:` from the active blockers.

Do not derive them from expected success.

See `### status: values` for the gate rule.

Select the next move from the current session state.

Name the easy-cheese skill and its argument.

Put the same target in the slug's `next:` field.

Suggest one best next step.

Suggest the following step when the path is clear.

For independent write tracks, set `mode: parallel` and `next: tasks`.

Put each exact skill invocation under `tasks:`.

Do not reduce parallel work to one sequential move.

For multiple read-only moves, use a `next:` list and `order:`.

| Where the session is | Suggest | `next:` |
| --- | --- | --- |
| Fuzzy idea without an approved spec | `/mold` | `mold` |
| Research needed before a decision or build | `/briesearch <question>` | `briesearch` |
| Discussion without writes | `/culture` | `culture` |
| Human decision blocks the next step | Show the decision and ask for direction | Set `status: gated:` |
| No action follows the checkpoint | Restore orientation and wait | `hold` |
| Approved spec without implementation | `/cook <spec-path>` | `cook` |
| Code without hardening or review | `/press <slug>`, then `/age` | `press` |
| Implementation needs review | `/age <ref>` | `age` |
| Review findings need fixes | `/cure <slug>` | `cure` |
| PR has review comments or failing CI | `/affinage <pr>` | `affinage` |
| Hard bug has no diagnosis | Show the blocker. Use `/pasteurize` when ready. | Set `status: gated:` |
| Work is complete | Record only | `done` |

When a phase stops, suggest the same phase with the slug.

The optional focus argument overrides the table.

Use it when the next session must not advance the pipeline.

## Required body sections by state

The default rule keeps only information that supports the resume.

The table defines the minimum `## Document` content.

It also defines one exception to the default rule.

| state | required Document sections |
| --- | --- |
| `status: gated:` | `## Decision dossier` per open fork: options / evidence `file:line` / what-each-breaks / prior leanings |
| `next: culture` | agenda + open-thread state |
| `next: cure` | findings artifact reference |
| `next: cook` / `press` / `age` | spec/slug pointers |
| `next: hold` / `done` | orientation only |

This dossier requirement overrides the just enough state compression rule for gated notes.
For `status: gated:`, keep complete information for each open decision.

Add one `## Decision dossier` entry for each open decision.

Include the options, `file:line` evidence, effects, and prior choice.

Do not reduce this information to the one-line status.

The resumed session uses the dossier to evaluate the decision.

See the structured-choice rules in [`../cheese/references/ask-user-question.md`](../cheese/references/ask-user-question.md).

## Do not duplicate

Keep the handoff short enough for a new agent to read.

Reference each durable artifact instead of copying it.

- Link specs, findings, and research reports under `.cheese/` by path.
- Link PRs, issues, commits, and diffs by URL or SHA.
- Link plans, ADRs, and design documents by path or URL.

Summarize an artifact only when the summary is shorter than the reference.

Do not copy a diff or spec into the handoff.

## Redaction

Remove API keys, tokens, passwords, connection strings, and personal information.

When the next session needs a secret, reference its location.

Use an environment variable name or secret manager path.

Never include the secret value.

## Handoff

Use `checkpoint` for normal intent JSON.

Use `commit` only for raw deltas and compaction proofs.

Both commands write the canonical record, its immutable revision, and the generated projection.

They do not make Git commits, pushes, PRs, or production code changes.

The commands report durability.

They never increase durability automatically.

Use read-only inspection capabilities.

Limit write access to the durable corpus and `.cheese/notes/**`.

The slug header keeps the shape that `src/easy_cheese/shared/handoff.py` parses.

The continuity codec does not change `parse_handoff_slug()` or its callers.

End with the slug orientation, a Markdown projection link, and repository-aware resume commands.

Keep the note link outside code fences.

Use this link form: `Wheypoint dropped: [.cheese/notes/<slug>.md](<absolute-note-path>)`.

From the original repository, run `cd <absolute-repo-path>`.

Then run `/cheese --continue <slug>`.

From another directory, run `/cheese --continue <absolute-repo-path>/.cheese/notes/<slug>.md`.

See the generated command list in [`references/commands.md`](references/commands.md).
