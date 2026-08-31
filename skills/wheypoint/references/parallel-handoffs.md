# Multi-move handoffs

Read this when one handoff has to start more than one next move: several read-only follow-ups through the inline `next:` list, or independent write efforts through `mode: parallel`. A single-move handoff needs none of it.

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

### `mode: parallel` and the `tasks:` block

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
