---
name: plate
description: >
  Turn finished local work into a commit, ordinary pull request, or pull-request stack.
  Use this skill to commit changes or publish a branch. Use it to open or update a PR.
  Use it to create, sync, restack, or submit a PR stack. You can also run /plate.
  This skill owns all staging, commits, pushes, PR creation, and stack changes.
  /gh owns GitHub inspection, reviews, comments, CI, issues, releases, and repository administration.
license: MIT
---

# /plate

Plate completes local work before review. It finishes required artifacts, validates, commits safely, and selects the correct publication path.

## Routing guard

Check ownership before you select a mode. `/plate` owns staging, commits, pushes, ordinary PR changes, and PR stack changes.

- `/plate` never performs code-quality review and never computes a review surface for its own sake. Review is `/age`.
- `/gh` owns GitHub inspection, reviews, comments, CI, merges, issues, workflows, releases, search, and administration.
  Use `/gh` when no local publication transaction is necessary.
- A request that only reads or assesses GitHub or diff state leaves `/plate` before any mode is selected.
  Thus, routing it here is a plate-owned failure.
- Destructive deletion, history rewrites, unsafe force-pushes, and protected-branch changes require explicit user authorization.

## Classify, then load one reference

Classify every invocation into exactly one mode. Load only that mode's reference. Do not read the others.

| Mode | Trigger | Load |
| --- | --- | --- |
| Commit-only | Save local work without publishing it | [`references/durable-writes.md`](references/durable-writes.md) |
| Topology preflight | Persist the new-PR layout before another workflow creates commits or branches | [`references/topology.md`](references/topology.md) |
| New PR | No PR exists for the branch and publication is requested | [`references/topology.md`](references/topology.md) |
| Existing PR | Update a PR while preserving its current topology | [`references/ordinary-pr.md`](references/ordinary-pr.md) |
| Stack maintenance | Create, inspect, sync, restack, submit, recover, or explicitly ship a stack | [`references/stacks.md`](references/stacks.md) |

Resolve topology before you continue new-PR work. Continue with the reference that topology selects.
Use `references/ordinary-pr.md` for single topology. Use `references/stacks.md` for stacked topology.
When an existing PR uses a stack, use `references/stacks.md`. Do not use a bare single-branch push.
Read provider instructions in [`gt.md`](references/gt.md), [`git-town.md`](references/git-town.md), and [`gh-stack.md`](references/gh-stack.md).
The stack reference selects one provider.

Accept `--hard` to run `/hard-cheese` immediately before you first share the work for review.
Give that gate the final artifact inventory and verification rows. Do not give it an earlier implementation snapshot.

## Tool routing

- Run `python3 skills/plate/scripts/plate.pyz stack-tools` before you select a stack provider.
  The command detects Graphite, Git Town, and `gh stack`. It does not change repository state.
- Use Git and GitHub for repository, remote, and PR state. Use the selected provider CLI for stack state.
- Use the repository code-intelligence backend to edit and read tracked artifacts.
  Follow this sequence from [`references/durable-writes.md`](references/durable-writes.md): fresh tagged read, one stale-safe write, diff read-back.
  Use named paths. Do not use shell redirects.
- Send durable wiki knowledge through `/wiki-ingest`. Do not edit the Hallouminate tree directly.
- Keep temporary completion and PR-body files under `.cheese/`. Do not stage them.

## Generic transaction

Commit-only work and ordinary PR work use this transaction. Stacked work uses the per-layer transaction in `references/stacks.md`.

1. **Final writing gate** — List every promised or required artifact. Write each artifact and read it back.
   Follow [`references/durable-writes.md`](references/durable-writes.md). Stop if a required write is missing or unverified.
2. **Validate** — Run the repository's shippability gate. Use `just check` in easy-cheese or any repository that defines it.
   Do not commit or publish when the gate fails.
3. **Inspect** — Read the status, complete diff, and recent log. Verify the intended file set.
4. **Stage** — Add only named files. Do not stage the full tree.
   Keep temporary `.cheese/` reports unstaged. Include tracked wiki and documentation changes.
   If the repository has a Hallouminate wiki, inspect `git status` for uncommitted `.hallouminate/wiki/` paths.
   Include writes from earlier in the session. Stage these writes unless Git ignores them.
   Publish wiki updates with this transaction. Do not publish them later.
5. **Commit** — Use a Conventional Commit message that explains the reason. Do not amend unless the user requests it.
   Do not bypass hooks.
6. **Verify** — Inspect the status and the committed file set.
7. **Publish when requested** — Follow [`references/ordinary-pr.md`](references/ordinary-pr.md). Read the PR after publication. Verify it.

Commit-only mode stops after verification. It does not push or open a PR.

## Commit contract

Before staging, inspect `git status`, the complete diff, and recent commits.
Reject credentials, `.env` files, and unexplained large binaries. Stage every intended path explicitly.
Use this format:

```text
type(scope): short description

Optional body when the rationale needs it.
```

Write the subject first and use a neutral tone. State the change first in the subject.
Put only required reviewer facts in the optional body. Keep the body short. Omit narrative prose, tone, and slang.

Use these types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, and `style`.
If a hook fails, fix the failure. Re-run the writing and quality gates when artifacts change.
Re-stage each named file. Create a new commit.

Use a single-quoted heredoc delimiter for multi-line commit messages. This delimiter protects backticks and dollar signs from shell interpolation.
Use an optional `Co-Authored-By: <name> <email>` trailer when the project accepts the harness identity. Otherwise, omit the trailer.
After staging, inspect the cached diff. An empty working diff can mean that all changes are staged.
Check the cached diff to distinguish this state from no changes.

Create one commit for each review unit. Use one commit for a single PR and one commit for each stack layer.
Do not shape a PR for commit-by-commit review. The system does not track approval for each commit.
Quality gates usually run only on the branch tip. Feedback on one commit delays the other commits.
Use multiple commits in one PR only for a short series of simple steps. Keep the combined change small.

## Halting

Every halt names the mode, the failed step, and who owns the failure.
Name the step with exactly one of: `classify`, `topology`, `durable write`, `quality gate`, `stage/commit`, `publish`, or `terminal validation`.

- **Plate-owned** — This skill selected an incorrect call shape or route.
  Examples include a malformed write, stale write, skipped read, or unnamed staging path.
  A full-tree staging path is also Plate-owned. A mismatch between the mode and reference is also Plate-owned.
  Work for `/age` or `/gh` is a Plate-owned routing error.
  Use this recovery rule: `Fix the call shape or the routing, then retry that step`.
- **Environment-owner** — Authentication, permission, hooks, network, provider enablement, or a shared backend caused the failure.
  Name the owning system in the report. Never retry it as if the call shape were wrong.
  Also, never weaken a gate, stage unnamed paths, or skip read-back to bypass the failure.

A failed quality gate proves that the work is not shippable. Therefore, halt at `quality gate` and fix the work.

## Completion

Write the terminal evidence to a temporary JSON file.
Run `python3 skills/plate/scripts/plate.pyz validate-publication <state.json>`.
Report completion only when the command returns normalized evidence with `valid: true`.

```json
{
  "mode": "new-pr",
  "topology": "single",
  "provider": "ordinary",
  "artifacts": [
    {"target": "docs/adr/example.md", "backend": "tilth", "verified": true}
  ],
  "gate": {"command": "just check", "result": "pass"},
  "commits": ["0123456789abcdef0123456789abcdef01234567"],
  "prs": [
    {
      "url": "https://github.com/example/repo/pull/42",
      "base": "main",
      "head": "feature",
      "verified": true
    }
  ],
  "risk": "none"
}
```

Use empty `commits` or `prs` lists when the selected mode does not create them.
Topology preflight stops before the publication transaction and quality gate.
Therefore, use `gate: {"command": "n/a", "result": "n/a"}` for topology preflight.

See the generated bundle command inventory in [`references/commands.md`](references/commands.md).
