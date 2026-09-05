# New-PR topology policy

Load this reference for the **topology preflight** and **new PR** modes. It resolves only the review shape.
Execution continues in `ordinary-pr.md` for a single PR or in `stacks.md` for a stacked chain.

For a **new PR**, resolve topology before any commit or branch-layout mutation:

1. Honor an explicit user choice from the current request or verified workflow state. It is authoritative.
   Persist the choice. Skip the topology question.
2. Otherwise inspect the finished work's review shape:
   - First classify each production change.
     Use **semantics-altering** for features, fixes, or externally observable contract changes.
     Use **semantics-preserving** for behavior-preserving refactors, internal moves, internal renames, or formatting-only changes.
     A diff containing both is never one review unit. Preserved behavior and changed behavior require different review scrutiny.
     Put incidental fixes in a separate change. Never put them in a feature or fix.
     A move or rename is semantics-altering if it changes an externally observable name, path, API, or configuration key.
     Use the same classification for a changed serialized shape, command, or documented contract.
   - Size never decides the shape on its own. It decides whether the question gets asked.
     When the semantics-altering surface exceeds roughly 400 changed code lines, always ask the single-versus-stacked question in step 3, even when the change reads as cohesive.
     Reviewer defect detection falls off sharply past that size (SmartBear/Cisco review data).
     At topology preflight, before a diff exists, estimate the surface from the spec or curd plan. Re-evaluate on the real diff at publication.
   - Choose **single** when the change is one cohesive review unit under that ceiling. Then proceed without asking.
     Its implementation, tests, docs, and durable artifacts must serve one behavior or contract.
     A split must not leave incomplete behavior. It must not force reviewers to reconstruct the whole.
   - Recommend **stacked** when the change has independently reviewable ordered layers.
     Give each layer a named purpose, its own validation, and a stable boundary.
     A lower layer must stand alone. Later layers must build on it without unrelated concerns.
     A change is also stack-sized when one review would combine distinct concerns with clear ordered boundaries.
     Put a semantics-preserving layer below a semantic change that depends on the reorganization.
     Over the ceiling with no layer boundary, recommend single, state the size risk, and still ask.
3. Ask one single-versus-stacked question when you recommend a stack, when the surface exceeds the ceiling, or when the review shape is genuinely ambiguous.
   For a stack recommendation, name the proposed layers. Recommend **Stacked PRs**.
   For ambiguity or an over-ceiling single, state the competing evidence. Recommend the best-supported option.
   Do not choose silently.

This policy stays unchanged under `--auto`. Transport any required question
through
[`../../cheese/references/ask-user-question.md`](../../cheese/references/ask-user-question.md).

```yaml
question:
  id: plate-layout
  prompt: How should this work be plated for review?
  recommended: <single | stacked>
  multi: false
  options:
    - id: single
      label: Single PR
      description: Keep the cohesive change as one branch and one review unit.
    - id: stacked
      label: Stacked PRs
      description: Split the named layers into ordered branches and dependent PRs.
```

## Answer normalization

The transport preserves an `Other` answer. It returns free text with an `other:` prefix.
Read the returned answer. Then apply these rules:

- Map the answer to `single` or `stacked` only when its text is unambiguous.
- Ask one clarification question for every other answer. Offer the same two options.
- Halt at `topology` when the clarification is also ambiguous. Report the answer.
- Persist only `single` or `stacked`. Never persist free text.

A supplied `pr_plan` is evidence for a stack recommendation. It can provide explicit commit and file boundaries.
It cannot override an explicit user choice or another verified topology resolution.
Ask for the split when stacked has no clear user or plan boundaries.
Do not invent the boundaries.

A prior `/plate` **topology preflight** for the same run is the resolution.
The resolution can be explicit, inferred as cohesive, or confirmed after a question.
Persist it as `plate_layout: single | stacked` in workflow state. Copy it into any later `pr_plan`.
At terminal publication, verify that both values agree. Reuse the resolution. Do not ask twice.
Apply this policy again when the record is missing, conflicting, or unverified. Do not ask automatically.

For an **Existing PR**, detect its ordinary or stacked topology. Do not ask the layout question.
Preserve that topology. Use its matching update path.
Commit-only isolated workers also do not ask because publication is out of scope.

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
