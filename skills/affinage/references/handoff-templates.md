# Handoff gate templates

Read this when rendering either handoff gate from `SKILL.md`.
Use the exact option text below.

## Cure selection gate

Show the recommended composite first.
Then show all five floor options in this order:

1. `all-medium, cheap`
2. `all`
3. `all-medium`
4. `all-high`
5. `all-blocker`

Use the labels and rules from [`../../age/references/handoff-detail.md`](../../age/references/handoff-detail.md).
Then show these options:

- **Pick findings to fix** — Accept `1,3,5`, floor names, `cheap`, `all`, `none`, or `skip N`.
- **Resolve merge conflicts** — Show this option only when the PR has conflicts.
  Check out the PR.
  Run `/melt`.
  Then show the gate again.
- **Stop — leave the report for later** — Treat this option as `none`.

Show all five floor options on every run.
Treat an empty selection as `none`.

## Reply approval gate

Show one batch gate before every `post-reply` call.
Show the gate after `/cure` returns.
Include every drafted reply in the gate.
A drafted reply is an applied reply, a deferred reply, a push-back draft, or an investigation note.
Read the applied and deferred replies from `.cheese/cure/pr-<n>.md`.

- **Post push-back drafts only** *(recommended)* — Post rejected drafts and hold every other reply.
- **Investigate now, then post** — Investigate each claim and post its actual result.
  Use `/pasteurize` for a regression test.
  Use `/briesearch` for evidence outside the diff.
- **Post all** — Post every applied reply, every deferred reply, and every push-back draft.
  Also post each specific investigation note without prior investigation.
- **Skip posting** — Post nothing and leave the report for later.
- **Per-finding** — Let the user select any drafted reply to post.
  Let the user also select a claim to investigate.

## Cure dispatch context

When the selection is not empty, send `/cure <slug> [--safe] [--open-pr] [--hard]` immediately.
Include this locked context:

```yaml
handoff_context:
  source_skill: /affinage
  source_report: .cheese/affinage/pr-<n>.md
  selection: "<verb or explicit ids>"
  resolved_ids: [<expanded ids>]
```

`/cure` confirms each selected identifier and applies the fixes.
It runs its `/age --scope` loop but does not run terminal `/plate`.
Affinage owns publication because `source_skill` is `/affinage`.
Pass `--safe`, `--open-pr`, and `--hard` to `/cure` when they apply.
