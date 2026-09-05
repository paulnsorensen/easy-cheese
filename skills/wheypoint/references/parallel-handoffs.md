# Multi-move handoffs

Use this contract when one handoff starts multiple moves.

This contract belongs to the handwritten legacy note.

The `checkpoint` command does not author `mode:`, `order:`, `parallel:`, or
`tasks:`. It refuses each key and names it in the error.

Write a multi-move handoff by hand under `.cheese/notes/`.

Use an inline `next:` list for read-only moves.

Use `mode: parallel` for independent write moves.

A single move does not need this contract.

## `next:` list form

Use a `next:` list for multiple read-only moves.

Include the required `order:` value.

```markdown
next: [briesearch "slug1", briesearch "slug2", culture "slug3"]
order: parallel | sequential
```

- Write each item as `<skill> "<arg>"`.
- Include `order:` when `next:` is a list.
- With `order: parallel`, `/cheese --continue` starts one read agent for each item.
- It starts all agents in the same turn.
- With `order: sequential`, the runtime runs items in their listed order.
- Use only `briesearch` or `culture` in an inline list.
- Use `mode: parallel` and isolated worktrees for parallel write tasks.
- Use `--auto` or the `/cook` fan pathway for sequential pipeline moves.

## `mode: parallel` and the `tasks:` block

Set `mode: parallel` and `next: tasks` for independent moves.

Add a `parallel:` block after the orientation line.

Then add a `tasks:` list.

Give each task its exact `command:`.

Commands can name different skills.

Never run parallel write tasks in one checkout.

Select one isolation strategy:

| `worktree_strategy` | Use when | Required fields |
| --- | --- | --- |
| `existing` | The user has durable bench checkouts | each write task has distinct `worktree:`, `branch:`, and `branch_from` |
| `create` | No checkouts exist | `worktree_root`, plus each write task has `branch:` and `branch_from` |
| `harness` | The host creates isolated worktrees | each write task has `branch:` and `branch_from`; the host creates the checkout |

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
    repo: /path/to/repository
    worktree: /path/to/worktree-01
    branch: user/kip-77-ai-test-server
    branch_from: origin/main
    command: /cook .cheese/specs/kip-77-ai-test-server.md
  - slug: kip-76-ai-service-spin-up
    intent: cook
    repo: /path/to/repository
    worktree: /path/to/worktree-02
    branch: user/kip-76-ai-service-spin-up
    branch_from: origin/main
    command: /cook .cheese/specs/kip-76-ai-service-spin-up.md
```

For a new setup, use `worktree_strategy: create`.

Add `worktree_root: ../.cheese-worktrees`.

`/cheese --continue` derives one checkout from each task slug.
