# Ordinary PR publication

Use this path only after the final writing gate, the green quality gate, named-file
staging, the commit, and the commit verification.
It covers the `single` shape and the `orthogonal_flat` shape (independent PRs off the trunk).

## New PR

1. Confirm that `/plate` resolved the new PR as `single`, or as one group of an `orthogonal_flat` resolution. Accept an explicit choice or the topology decision.
2. Resolve the trunk and current branch. Reject publication from the trunk.
3. Draft a title and body per `## Body contract` below.
4. Write the body to a temporary or transient file. Pass that file through `--body-file`.
   Do not embed a markdown heredoc in `--body`.
   Then run `python3 skills/plate/scripts/plate.pyz check-pr-body --body-file <body-path>`.
   Add `--template-file .github/PULL_REQUEST_TEMPLATE.md` when the repository tracks that template.
   Add `--stack-layer` for a stack layer. Fix every reported error and run the check again.
   Do not create or edit the PR until the check exits 0.
5. Push the named branch without force. Follow `## Push verification` before the next step.
6. Create the PR with an explicit base and head:

   ```bash
   gh pr create --title "<title>" --body-file <body-path> --base <base> --head <head>
   ```

7. Verify with `gh pr view --json number,url,title,baseRefName,headRefName,state`.

Do not use `--fill` when it would omit artifact or verification details.

## Independent PRs

Use this section for the `orthogonal_flat` shape. Base every group on the trunk. A group has no `depends_on`.
Record the evidence as topology `stacked`, provider `ordinary`, and a `pr_plan` with shape `orthogonal_flat`.
`validate-publication` accepts provider `ordinary` with topology `stacked` only for that plan shape.
Emit the carving commands once: `python3 skills/plate/scripts/plate.pyz carve-flat --source-branch <source> --pr-plan <plan-path>`.
The JSON `groups` list follows plan order. Each entry holds `branch`, `base`, `carve`, and `restore`.
For each group, in plan order:

1. Run the group's `carve` commands. They create the branch from the trunk and cherry-pick its commits in order.
   When one commit mixes groups, check out the group's whole files from the source branch and create a new commit instead of the cherry-pick.
2. Run the quality gate on the group branch. Halt at `quality gate` for that group when it fails.
3. Publish the group as a `## New PR`. Its body describes only its own group.
4. Run the group's `restore` command before the next group.

Leave the source branch unchanged. Report every PR URL in plan order.

## Existing ordinary PR

Detect the PR with `gh pr view --json number,baseRefName,headRefName,url`. Then inspect the provider metadata.
A stacked topology leaves this file for `stacks.md`.
Read the base and head with `gh pr view`. Commit the validated named files.
Push the exact head branch. Then read the PR back.
Update the title or body only when the new work makes existing metadata inaccurate.
To move part of the PR into a separate PR, create a new `orthogonal_flat` branch from the trunk.
Removing that part from the existing branch rewrites published history. It needs explicit user authorization.

## Failures

Authentication or permission failures halt publication. Report the exact command and error.
A rejected push does not permit a force-push. Fetch and explain the divergence.
Never create a duplicate PR when one already exists.

## Metadata and lifecycle

Publication-relevant GitHub operations remain here:

- Add `--draft` when explicitly requested.
- Add `--reviewer <login>` or `--assignee <login>` only from the supplied
  publication metadata.
- Use `gh pr edit <number> --title <title> --body-file <path>` when verified
  commits make existing metadata inaccurate. Run `check-pr-body` on that file first.
- Use `gh pr ready <number>` only when asked to publish a draft.
- Use `gh pr checks` to verify publication context. CI triage, review, comments,
  and merge stay outside `/plate`. Use the `gh` CLI directly for that work.

Query the current head for an existing PR before creation.
If a PR exists, switch to the existing-PR path. Do not rely on a failed create call.

## Body contract

A reviewer reads a short body. Agent-written bodies that claim changes the diff lacks lose reviewer trust.
When the repository tracks `.github/PULL_REQUEST_TEMPLATE.md`, use its section headings.
Otherwise use `## Why`, `## What changed`, `## Non-obvious changes`, `## How to verify`, and `## Risk`.
`check-pr-body` enforces the 40-line cap, the required headings, the `Plated as` line, the filler-word ban,
and, for a stack layer, the `Stack: <n> of <total>` line and the stack-order flowchart.
The 20-line cap for a small change, the claims, and the reading order stay a judgment call.
Keep the body file transient unless the repository tracks PR templates or release artifacts.
Leave a transient body file unstaged after verification.

Length and tone:

- Count non-blank lines. Do not count one diagram or the checklist of a repository PR template.
- Keep the body at 40 lines or fewer. Keep a small change at 20 lines or fewer.
- Give each prose section one to three sentences or bullets. Write `None` for an empty template section.
- Open with why in one or two sentences.
- Do not restate the diff or list every file. When the change exceeds about 200 lines or 5 files, give a reading order.
- Use plain words. Do not use filler such as comprehensive, robust, seamless, leverage, significantly, or dramatically.
- Rewrite a supplied draft body. Keep only the facts that the evidence supports.

Claims:

- Name a change only when the net diff contains it. A reverted commit is not a change.
- List each verification as one line: the command and its result (`pass`, `fail`, or `not run`).
  List only checks that ran in this session. List a relevant check that did not run as `not run`.
  Never claim a benchmark, platform, harness, or speedup that no command measured.
- Link the spec, plan, or spike branch, and list deferred follow-ups, when they exist.
- A semantics-preserving change says so in its first line. It names the mechanism and states the invariant to verify.
  Examples include a behavior-preserving refactor, an internal move, an internal rename, or a formatting-only change.
  For example, a move states that it drops nothing and duplicates nothing.
- A semantics-altering change names the changed behavior or contract and its observable verification.
  A logic change names the test that fails before the change.
- A `## Non-obvious changes` section names every hunk whose intent is not visible from the diff alone, with one line of reason each.
  Write `None` when every hunk is self-evident. Author-annotated reviews carry markedly lower defect density (Cisco review data).
- List generated files, such as `.pyz` archives and lockfiles, as generated. Tell the reviewer to skip them.
- Add the topology line `Plated as <shape>: <reason>`. A stack layer adds `Stack: <n> of <total>`, with the PRs below and above it.
  An independent PR does not describe the other groups.
- State size risk, a weakened check, or a landing-shape deviation under the risk section.

### Diagram

Add one Mermaid diagram only when the structure is the point of the review:

| Change | Diagram |
| --- | --- |
| A data or control flow that crosses three or more modules | `flowchart` of that flow |
| A changed message order between components or agents | `sequenceDiagram` |
| A stack of PRs | `flowchart` of the stack order, with this PR marked |

Add no diagram to a small fix, a docs-only change, or an independent PR.
Derive the diagram from the diff. Show only components that the diff changes, plus their direct callers.
Keep it to 15 nodes or fewer. Quote a label that holds punctuation, for example `R["router.select()"]`.
Never use `end` as a node id. Use `<br>` for a line break. Do not add theme or style directives.

## Push verification

Read the remote and upstream before pushing. Push the exact named head branch.
Do not pipe `git push` into another command; a pipe hides its exit status.
Read the exit status. Then confirm the remote head with `git ls-remote --heads <remote> <branch>`.
The remote head SHA must equal the local head SHA before `gh pr create`.
A failed or unverified push halts at `publish`. An authentication failure is environment-owned.
Verify local status. Verify the PR head and base.
A successful CLI exit without a matching PR head SHA is incomplete.
