---
name: plate
description: >
  Turn finished local work into a commit, an ordinary pull request, or a
  stacked pull-request chain. Use when asked to commit, save changes, open or
  update a PR, publish a branch, create/sync/restack/submit a PR stack, or run
  /plate. Owns all staging, committing, pushing, PR creation, and stack-aware
  mutation. GitHub inspection, review, comments, CI, issues, releases, and
  repository administration remain /gh.
license: MIT
---

# /plate

Plate is the final local-to-review transaction: finish required artifacts,
validate, commit safely, then publish through the repository's ordinary or
stack-aware path.

## Routing guard

Check ownership before selecting a mode. `/plate` owns staging, commits,
pushes, ordinary PR creation and update, and stack creation, update, sync, and
recovery.

- `/plate` never performs code-quality review and never computes a review
  surface for its own sake. Review is `/age`.
- GitHub inspection, review, comments, CI, ordinary merge, issues, workflows,
  releases, search, and administration are `/gh` when no local publication
  transaction is required.
- A request that only reads or judges GitHub or diff state leaves `/plate`
  before any mode is selected; routing it here is a plate-owned failure.
- Destructive deletion, history rewrites, force-push outside a provider's
  lease-safe stack flow, and protected-branch mutation require explicit user
  authorization.

## Classify, then load one reference

Classify every invocation into exactly one mode, then load that mode's single
reference. Do not read the others.

| Mode | Trigger | Load |
| --- | --- | --- |
| Commit-only | Save local work without publishing it | [`references/durable-writes.md`](references/durable-writes.md) |
| Topology preflight | Persist the new-PR layout before another workflow creates commits or branches | [`references/topology.md`](references/topology.md) |
| New PR | No PR exists for the branch and publication is requested | [`references/topology.md`](references/topology.md) |
| Existing PR | Update a PR while preserving its current topology | [`references/ordinary-pr.md`](references/ordinary-pr.md) |
| Stack maintenance | Create, inspect, sync, restack, submit, recover, or explicitly ship a stack | [`references/stacks.md`](references/stacks.md) |

New-PR work resolves topology first, then continues into the reference that
resolution names: `references/ordinary-pr.md` for single, `references/stacks.md`
for stacked. An existing PR whose detected topology is a stack uses
`references/stacks.md`, never a bare single-branch push. Provider execution
detail lives in [`gt.md`](references/gt.md),
[`git-town.md`](references/git-town.md), and
[`gh-stack.md`](references/gh-stack.md); the stack reference selects among them.

Accept `--hard` to run `/hard-cheese` immediately before the first
share-for-review operation. Give that gate the final artifact inventory and
verification rows, not an earlier implementation-only snapshot.

## Tool routing

- Run `python3 skills/plate/scripts/plate.pyz stack-tools` before
  selecting a stack provider. It probes Graphite, Git Town, and `gh stack`
  without mutating repository state.
- Use Git and GitHub or the selected provider CLI for repository, remote, PR,
  and stack state.
- Use the repository code-intelligence backend for tracked artifact edits and
  read-back, following the canonical write sequence in
  [`references/durable-writes.md`](references/durable-writes.md): fresh tagged
  read, one stale-safe write, diff read-back. Use named paths, never shell
  redirects.
- Route durable wiki knowledge through `/wiki-ingest`; never hand-edit the
  Hallouminate tree.
- Keep transient completion and PR-body files under `.cheese/` and unstaged.

## Generic transaction

Commit-only and ordinary PR work use this transaction. Stacked work uses the
per-layer transaction in `references/stacks.md`.

1. **Final writing gate** — inventory, write, and read back every promised or
   required artifact using
   [`references/durable-writes.md`](references/durable-writes.md). Halt if
   any required write is missing or unverified.
2. **Validate** — run the repository's shippability gate. In easy-cheese and
   any repo that defines it, this is `just check`. Never commit or publish on
   red.
3. **Inspect** — read status, diff, and recent log; verify the intended file
   set.
4. **Stage** — add named files only. Never stage the whole tree. Keep transient
   `.cheese/` reports unstaged; include tracked wiki/docs writes. When the repo
   has a hallouminate wiki, sweep `git status` for uncommitted
   `.hallouminate/wiki/` paths — including writes from earlier in the session —
   and stage them unless gitignored. Wiki updates ship with this publication,
   never after it.
5. **Commit** — use a Conventional Commit message focused on why. Do not amend
   unless explicitly requested and do not bypass hooks.
6. **Verify** — inspect status and the committed file set.
7. **Publish when requested** — use
   [`references/ordinary-pr.md`](references/ordinary-pr.md), then read the PR
   back and verify it.

Commit-only mode stops after verification. It never pushes or opens a PR.

## Commit contract

Before staging, inspect `git status`, the complete diff, and recent commits.
Reject credentials, `.env` files, and unexplained large binaries. Stage every
intended path explicitly. Use:

```text
type(scope): short description

Optional body when the rationale needs it.
```

Write the message BLUF and newscaster-flat: the subject states the change up
front, the optional body carries only the facts a reviewer needs, and nothing
else — short, concise, no narrative prose, tone, or slang.

Allowed types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`,
`style`. If a hook fails, fix it, re-run the writing and quality gates when
artifacts changed, re-stage named files, and create a new commit.

Use a single-quoted heredoc delimiter for multi-line commit messages so shell
interpolation cannot alter backticks or dollar signs. An optional
`Co-Authored-By: <name> <email>` trailer may use the harness identity when the
project accepts it; otherwise omit it. After staging, inspect the cached diff.
If the working diff is empty, distinguish "nothing to commit" from "everything
is staged" by checking the cached diff.

Structure one commit per review unit: one for a single PR, one per stack
layer. Do not shape a PR for commit-by-commit review — per-commit approval
state is untracked, quality gates usually run only on the branch tip, and
feedback on any one commit holds the rest hostage. Multiple commits in one PR
are reserved for a short series of simple, non-controversial steps that stay
small taken together.

## Halting

Every halt names the mode, the failed step, and who owns the failure. Name the
step with exactly one of: `classify`, `topology`, `durable write`,
`quality gate`, `stage/commit`, `publish`, `terminal validation`.

- **Plate-owned** — a call this skill shaped or routed wrong: a malformed or
  stale code-intelligence write, a skipped fresh read or read-back, an unnamed
  or whole-tree staging path, a mode/reference mismatch, or work routed here
  that belongs to `/age` or `/gh`. Fix the call shape or the routing, then
  retry that step.
- **Environment-owner** — authentication, permission, hook, network, provider
  enablement, or shared-backend failure. Report it with the owning system
  named. Never retry it as if the call shape were wrong, and never weaken a
  gate, stage unnamed paths, or skip read-back to get past it.

A red quality gate is environment-neutral evidence that the work is not
shippable: halt at `quality gate` and fix the work.

## Completion

Write the terminal evidence to a transient JSON file, then run
`python3 skills/plate/scripts/plate.pyz validate-publication <state.json>`.
Report completion only when it returns normalized evidence with `valid: true`.

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
Topology preflight uses `gate: {"command": "n/a", "result": "n/a"}` because it
stops before the publication transaction and quality gate.
