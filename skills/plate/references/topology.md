# New-PR topology policy

Load this reference for the **topology preflight** and **new PR** modes. It resolves only the review shape.
Execution continues in `ordinary-pr.md` for `single` and `orthogonal_flat`, or in `stacks.md` for a stacked chain.

Plate decides the review shape. It does not ask the user.
A layout question delays publication and adds no information: in past sessions, users took the recommended option every time.
This policy is unchanged under `--auto`.
Resolve the shape before any commit or branch-layout mutation.

## Decide the shape

1. Honor an explicit user choice from the current request, verified workflow state, or the spec's `landing` block. It is authoritative.
   Derive the topology from `landing.shape` via `easy_cheese_schemas.manifest.plate_layout_for`, with `landing.layers` as the proposed layer boundaries.
   A choice of shape without boundaries ("make this a stack") still needs boundaries. Derive them with step 3.
2. Classify each production change:
   - Use **semantics-altering** for features, fixes, or externally observable contract changes.
   - Use **semantics-preserving** for behavior-preserving refactors, internal moves, internal renames, or formatting-only changes.
   - A diff containing both is never one review unit. Preserved behavior and changed behavior require different review scrutiny.
   - A move or rename is semantics-altering if it changes an externally observable name, path, API, or configuration key.
     Use the same classification for a changed serialized shape, command, or documented contract.
3. Partition the work into parts. A part is a set of commits or whole files with one purpose.
   Use only existing commit boundaries or whole-file partitions. Never manufacture a boundary that splits a hunk or rewrites a commit.
   Merge parts that edit the same hunks into one part. This rule overrides a spec that asks for one PR per issue; state why.
   Tests, docs, and durable artifacts join the part whose decision they verify or describe.
   A generated artifact, such as a `.pyz` archive or a lockfile, joins the part whose source generates it.
   An incidental fix that is unrelated to the main change is its own part.
4. Choose the first row that matches:

   | Evidence | Shape |
   | --- | --- |
   | One part: one cohesive review unit that serves one behavior or contract | `single` |
   | A split needs a history rewrite, or a lower part fails the quality gate alone | `single` |
   | Two or more parts that share no file, import, or configuration, and each applies to the trunk alone | `orthogonal_flat` |
   | Ordered parts where each later part depends on an earlier part, and each part passes the gate on its parent | `stacked_linear` |
   | Independent parts mixed with a dependent chain | `stacked_linear` for the chain; then publish each independent part as its own `single` PR in a separate Plate transaction |

   Put a semantics-preserving part below the semantic change that depends on its reorganization.
   Never stack parts that do not depend on each other. Independent parts merge and revert alone.
5. Size never decides the shape on its own.
   When the semantics-altering surface exceeds roughly 400 changed code lines, look again for clean boundaries.
   Reviewer defect detection falls off sharply past that size (SmartBear/Cisco review data).
   With no clean boundary, choose `single`. State the size risk in the PR body and give a reading order.
   At topology preflight, before a diff exists, estimate the parts from the spec or curd plan. Re-evaluate on the real diff at publication.
6. Record the decision as one line in the completion report and the PR body: `Plated as <shape>: <reason>`.
   Proceed without asking.

A `landing` block that the finished diff cannot meet does not stop publication.
A layer that depends on files a later layer owns, or commits that cannot split on the layer boundaries, is a conflict.
Re-layer on the clean boundaries from step 3 when they exist. Otherwise collapse to `single`.
State the deviation in the PR body. The statement names the layer and the files in conflict.
Never ask the plain layout question while a `landing` block exists, and never ask it without one.

## Plan and persistence

A supplied `pr_plan` is evidence for the decision. It can provide explicit commit and file boundaries.
It cannot override an explicit user choice or another verified topology resolution.
Repair a malformed plan instead of halting: map a legacy `stacked` shape to `stacked_linear` and add the v1 `contract_version` block.
Keep the plan's groups, branches, and bases when they satisfy step 3.

A prior `/plate` **topology preflight** for the same run is the resolution. Reuse it. Do not decide twice.
Persist it as `plate_layout: single | stacked` in workflow state. `stacked` covers every multi-PR shape.
Choose the `pr_plan` `shape` from this resolution: `single`, `orthogonal_flat`, or `stacked_linear`.
`plate_layout_for` projects `plate_layout` from `shape`, not the other way. The v1 plan never carries `plate_layout`.
At terminal publication, verify that both values agree.
Apply this policy again when the record is missing, conflicting, or unverified.

For an **Existing PR**, detect its ordinary or stacked topology. Do not ask the layout question.
Preserve that topology. Use its matching update path.
A request to move part of an existing PR into a separate PR creates a new `orthogonal_flat` branch from the trunk.
Removing that part from the existing branch rewrites published history, so it needs explicit user authorization.
Commit-only isolated workers do not decide topology because publication is out of scope.

Topology preflight persists the resolution. It reads the resolution back.
It stops before any commit, branch mutation, push, or PR operation.

## Repair-worktree topology

The branch name is `worktree-agent-repair-*`. Apply the policy above to any other branch.

The repair handoff must carry `run_branch`. This field names the verified run branch.
Halt at `topology` when `run_branch` is absent. A missing field is not evidence of a deleted branch.

Then run the mechanical file-overlap check.
See [`../../cook/references/quality-gates.md`](../../cook/references/quality-gates.md) § Repair pathway.
Compute the overlap with one command:

```bash
git diff --name-only --find-renames "$(git merge-base <run-branch> <repair-branch>)" <repair-branch>
```

Compare that path set with the same command run for `<run-branch>`. The shared paths are the overlap.
Count the changed lines of each shared path with `git diff --numstat` over the same range.
Count a rename as its changed lines only. Count a binary path as one changed line.
Halt at `topology` when `--numstat` reports `-` for a path that is not binary.

Then select the topology:

- Publish an ordinary independent pull request against `main` when there are no shared paths.
- Verify branch deletion with `git rev-parse --verify <run-branch>` before you use the independent path for a missing run branch.
  Halt at `topology` when the command cannot decide.
- Move shared files onto the run branch at or below the small-repair threshold. Do not publish these files independently.
  Cook owns the harvest command. Run the harvest through `/cook`.
  See [`../../cook/references/quality-gates.md`](../../cook/references/quality-gates.md).
  Resolve `<run-worktree>` from verified Git worktree state. Halt at `topology` when the harvest fails.
- Restack with the repair as the base pull request above the threshold. Use the stack process in `stacks.md`.
