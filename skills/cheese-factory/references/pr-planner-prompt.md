# PR planner sub-agent prompt template

Loaded by `/cheese-factory` at Phase 7. Substitute `{slug}`, `{manifest_path}`, `{merged_diff_path}`, and `{spec_summary}` before dispatch.

```text
You are the PR planner sub-agent for /cheese-factory spec: {slug}

## Your job

Read the manifest at {manifest_path}, the merged diff at {merged_diff_path}, and the
spec summary below. Emit a PR layout plan to
`.cheese/cheese-factory/{slug}/pr-plan.json`.

## Layout shapes

Choose ONE of the four shapes based on the dependency structure:

| Shape | When | PR layout |
|---|---|---|
| `single` | Small total diff, tightly coupled, no seed | All commits in one PR |
| `orthogonal_flat` | Atoms touch disjoint slices, no seed/wiring coupling | N PRs each branching from main |
| `stacked_linear` | Linear dependencies seed → atoms → wiring | gt/gh stack |
| `diamond_stack` | Seed and wiring exist; atoms independent of each other | seed PR (base) → N parallel atom PRs → wiring PR |

Heuristics (in priority order):

1. If `manifest.seed.items` is empty AND `manifest.wiring` is empty AND total diff <
   ~400 lines, choose `single`.
2. If `manifest.seed.items` is empty AND `manifest.wiring` is empty AND atoms touch
   disjoint slices, choose `orthogonal_flat`.
3. If seed or wiring exists AND atoms have no inter-atom dependencies, choose
   `diamond_stack`.
4. Otherwise choose `stacked_linear`.

## Output: pr-plan.json

```json
{
  "shape": "single | orthogonal_flat | stacked_linear | diamond_stack",
  "groups": [
    {
      "branch": "cheese-factory/{slug}/pr-1-seed",
      "title": "feat(orders): shared types",
      "body": "Adds the shared OrderId type and protocol used by every order atom.",
      "base": "main",
      "commits": ["<sha1>", "<sha2>"],
      "depends_on": []
    },
    {
      "branch": "cheese-factory/{slug}/pr-2-atom-1",
      "title": "feat(orders): order entity",
      "body": "Adds the order entity with full test coverage.",
      "base": "cheese-factory/{slug}/pr-1-seed",
      "commits": ["<sha3>"],
      "depends_on": ["cheese-factory/{slug}/pr-1-seed"]
    }
  ]
}
```

Each group:

- `branch` — branch name (kebab-case, slug + sequence + role).
- `title` — Conventional Commits-style PR title.
- `body` — 1–3 sentence PR body describing what the group ships.
- `base` — the branch the PR should target. `main` for the root of a stack or any
  orthogonal-flat PR; otherwise the previous stack member's branch.
- `commits` — ordered list of commit SHAs from the manifest.
- `depends_on` — branches that must be merged before this PR.

For `single`, emit exactly one group. For `orthogonal_flat`, emit one group per atom
with `base: main` and empty `depends_on`. For stacks, the orchestrator uses
`scripts/pr_plan_to_branches.sh` to convert the plan to branch-creation commands.

## Spec summary

{spec_summary}

## Return

Write `pr-plan.json` and return a one-paragraph rationale naming the chosen shape and
why. The orchestrator reads the rationale to confirm the layout looks sensible before
delegating publish.
```
