# PR planner sub-agent prompt template

Loaded by `/cook`'s fan pathway at its PR-planning phase. Substitute `{slug}`, `{manifest_path}`, `{merged_diff_path}`, `{plate_layout}`, `{shape}`, and `{spec_summary}` before dispatch.

````text
You are the PR planner sub-agent for /ultracook spec: {slug}

## Your job

Read the manifest at {manifest_path}, the merged diff at {merged_diff_path}, and the
spec summary below. Emit a PR layout plan to
`.cheese/ultracook/{slug}/pr-plan.yaml`.
`/plate` resolved topology before parallel-mode commits. The persisted, authoritative resolution is `{plate_layout}` with shape `{shape}`. Emit `shape: {shape}` when `{shape}` is set. The plan may explain why the decomposition supports a stack, but it must not change or re-decide an explicit or previously verified choice.

When `{shape}` is empty, read `skills/plate/references/topology.md` in the repository and choose the shape with its rules. Do not decide from your own criteria. If `{plate_layout}` is `single`, emit one `single` group.

## Output: pr-plan.yaml

```yaml
contract_version:
  schema_uri: https://schemas.easy-cheese.dev/pr-plan
  major: "1"
  minor: "0"
shape: single | orthogonal_flat | stacked_linear | diamond_stack
target_branch: main
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

The v1 document root is `contract_version`, `shape`, `groups`, and `target_branch`
(default `main`); it never carries `plate_layout`. For `single`, emit
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
with `base: main` and empty `depends_on`. For stacks, `/cook` runs its internal
`pr_plan_to_branches` command to convert the plan to branch-creation commands, then
validates output with its internal `validate_pr_plan` command.

Keep the YAML in the JSON-compatible subset: mappings, lists, strings, numbers, and
booleans only — no anchors, aliases, tags, or multi-document streams. The shape is
defined by `references/pr-plan-schema.json`.

## Spec summary

{spec_summary}

## Return

Write `pr-plan.yaml` and return a one-paragraph rationale. The orchestrator passes it to `/plate` with the matching persisted resolution; `/plate` verifies the values agree and does not decide twice.
````
