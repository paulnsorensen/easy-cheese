# Multi-move handoffs

Use this contract when one checkpoint starts multiple moves.

`tasks` and `parallel` are `CheckpointIntent` fields; see [`intent-contract.md`](intent-contract.md).

Set `next: tasks` and give at least one task.

The projection then renders `mode: parallel` after `artifact:` and a `## Tasks` section.

A single move does not need this contract.

## `parallel` and `tasks`

Give each task its exact `command`; commands can name different skills.

Never run parallel write tasks in one checkout.

Select one isolation strategy:

| `worktree_strategy` | Use when | Required fields |
| --- | --- | --- |
| `existing` | The user has durable bench checkouts | each write task has distinct `worktree`, `branch`, and `branch_from` |
| `create` | No checkouts exist | `worktree_root`, plus each write task has `branch` and `branch_from` |
| `harness` | The host creates isolated worktrees | each write task has `branch` and `branch_from`; the host creates the checkout |

Intent example:

```json
{
  "work_id": "kip-ai",
  "orientation": "KIP-76 and KIP-77 are ready to run as independent PR efforts.",
  "next": "tasks",
  "parallel": {"isolation": "git-worktree", "worktree_strategy": "existing"},
  "tasks": [
    {"slug": "kip-77-ai-test-server", "intent": "cook", "repo": "/path/to/repository",
     "worktree": "/path/to/worktree-01", "branch": "user/kip-77-ai-test-server",
     "branch_from": "origin/main", "command": "/cook .cheese/specs/kip-77-ai-test-server.md"},
    {"slug": "kip-76-ai-service-spin-up", "intent": "cook", "repo": "/path/to/repository",
     "worktree": "/path/to/worktree-02", "branch": "user/kip-76-ai-service-spin-up",
     "branch_from": "origin/main", "command": "/cook .cheese/specs/kip-76-ai-service-spin-up.md"}
  ]
}
```

Rendered projection preamble and tasks block:

```markdown
status: ok
next: tasks
artifact:
mode: parallel
KIP-76 and KIP-77 are ready to run as independent PR efforts.

## Tasks

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

For a new setup, use `worktree_strategy: create` and add `worktree_root`.

`/cheese --continue` derives one checkout from each task slug.

## Read-only moves in a legacy note

A handwritten legacy note may list read-only moves with `next: [briesearch "slug1", culture "slug2"]`.

With `order: parallel`, `/cheese --continue` starts one read agent per item in the same turn; with `order: sequential`, it runs them in listed order.

See [`legacy-notes.md`](legacy-notes.md).
