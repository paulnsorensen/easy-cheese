# PR planner sub-agent prompt template

Loaded by `/ultracook` at Phase 7. Substitute `{slug}`, `{manifest_path}`, `{merged_diff_path}`, `{plate_layout}`, and `{spec_summary}` before dispatch.

````text
You are the PR planner sub-agent for /ultracook spec: {slug}

## Your job

Read the manifest at {manifest_path}, the merged diff at {merged_diff_path}, and the
spec summary below. Emit a PR layout plan to
`.cheese/ultracook/{slug}/pr-plan.yaml`.
`/plate` resolved topology before parallel-mode commits. The persisted, authoritative resolution is `{plate_layout}`. Copy it exactly into the plan. The plan may explain why the decomposition supports a stack, but it must not change or re-ask an explicit or previously verified choice.

## Layout shapes

Choose ONE of the four shapes based on the dependency structure:

| Shape | When | PR layout |
|---|---|---|
| `single` | The persisted choice is single; all groups form one cohesive review unit | All commits in one PR |
| `orthogonal_flat` | The persisted choice is stacked; curds are independently reviewable with no ordering dependency | N PRs each branching from main |
| `stacked_linear` | The persisted choice is stacked; reviewable layers have linear dependencies | provider selected by `/plate` |
| `diamond_stack` | The persisted choice is stacked; a shared base and final wiring surround independent curds | seed PR (base) → N parallel curd PRs → wiring PR |

Review-shape criteria, in priority order:

1. If `{plate_layout}` is `single`, emit one `single` group. The persisted
   choice is authoritative even when the decomposition could support a stack.
2. For `stacked`, identify layers with a named purpose, their own validation,
   and a stable boundary that lets each layer be reviewed independently.
3. Use `orthogonal_flat` only when curds have no ordering dependency. Use
   `diamond_stack` when a shared base and final wiring surround independent
   curds. Otherwise use `stacked_linear`.
4. Do not use line-count or file-count thresholds. If the plan cannot name
   honest review boundaries, report the conflict instead of manufacturing them.

## Output: pr-plan.yaml

```yaml
plate_layout: single | stacked
shape: single | orthogonal_flat | stacked_linear | diamond_stack
groups:
  - branch: ultracook/{slug}/pr-1-seed
    title: "feat(orders): shared types"
    body: Adds the shared OrderId type and protocol used by every order curd.
    base: main
    commits:
      - <sha1>
      - <sha2>
    depends_on: []
  - branch: ultracook/{slug}/pr-2-curd-1
    title: "feat(orders): order entity"
    body: Adds the order entity with full test coverage.
    base: ultracook/{slug}/pr-1-seed
    commits:
      - <sha3>
    depends_on:
      - ultracook/{slug}/pr-1-seed
```

`plate_layout` must equal `{plate_layout}` from the manifest. For `single`, emit
exactly one `single` group. For `stacked`, emit an ordered multi-PR shape and
explicit commit/file boundaries; place shared durable writes in the
bottom/common group or an explicit wiring group.

Each group:

- `branch` — branch name (kebab-case, slug + sequence + role).
- `title` — Conventional Commits-style PR title.
- `body` — 1–3 sentence PR body describing what the group ships.
- `base` — the branch the PR should target. `main` for the root of a stack or any
  orthogonal-flat PR; otherwise the previous stack member's branch.
- `commits` — ordered list of commit SHAs from the manifest.
- `depends_on` — branches that must be merged before this PR.

For `single`, emit exactly one group. For `orthogonal_flat`, emit one group per curd
with `base: main` and empty `depends_on`. For stacks, the orchestrator runs
`${CLAUDE_SKILL_DIR}/scripts/ultracook.pyz pr_plan_to_branches` to convert the plan to
branch-creation commands. The orchestrator validates your output with
`${CLAUDE_SKILL_DIR}/scripts/ultracook.pyz validate_pr_plan` before running the branch converter.

Keep the YAML in the JSON-compatible subset: mappings, lists, strings, numbers, and
booleans only — no anchors, aliases, tags, or multi-document streams. The shape is
defined by `references/pr-plan-schema.json`.

## Spec summary

{spec_summary}

## Return

Write `pr-plan.yaml` and return a one-paragraph rationale. The orchestrator passes it to `/plate` with the matching persisted resolution; `/plate` verifies the values agree and does not ask twice.
````
