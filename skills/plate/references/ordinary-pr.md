# Ordinary PR publication

Use this path only after the final writing gate, the green quality gate, named-file
staging, the commit, and the commit verification.
It covers the `single` shape and the `orthogonal_flat` shape (independent PRs off the trunk).

## New PR

1. Confirm that `/plate` resolved the new PR as `single`. Accept an explicit choice or the topology decision.
2. Resolve the trunk and current branch. Reject publication from the trunk.
3. Draft a title and body per `## Body contract` below.
4. Write the body to a temporary or transient file. Pass that file through `--body-file`.
   Do not embed a markdown heredoc in `--body`.
5. Push the named branch without force. Follow `## Push verification` before the next step.
6. Create the PR with an explicit base and head:

   ```bash
   gh pr create --title "<title>" --body-file <body-path> --base <base> --head <head>
   ```

7. Verify with `gh pr view --json number,url,title,baseRefName,headRefName,state`.

Do not use `--fill` when it would omit artifact or verification details.

## Independent PRs

Use this section for the `orthogonal_flat` shape. Every group is based on the trunk and has no `depends_on`.
For each group, in plan order:

1. Create the group branch from the trunk: `git switch -c <branch> <trunk>`.
2. Cherry-pick the group's commits in their original order.
   When one commit mixes groups, check out the group's whole files from the source branch and create a new commit.
3. Run the quality gate on the group branch. Halt at `quality gate` for that group when it fails.
4. Publish the group as a `## New PR`. Its body describes only its own group.
5. Return to the source branch before the next group.

Leave the source branch unchanged. Report every PR URL in plan order.

## Existing ordinary PR

Detect the PR with `gh pr view --json number,baseRefName,headRefName,url`. Then inspect the provider metadata.
A stacked topology leaves this file for `stacks.md`. Do not ask the layout question.
Read the base and head with `gh pr view`. Commit the validated named files.
Push the exact head branch. Then read the PR back.
Update the title or body only when the new work makes existing metadata inaccurate.

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
  commits make existing metadata inaccurate.
- Use `gh pr ready <number>` only when asked to publish a draft.
- Use `gh pr checks` to verify publication context. CI triage, review, comments,
  and merge stay outside `/plate`. Use the `gh` CLI directly for that work.

Query the current head for an existing PR before creation.
If a PR exists, switch to the existing-PR path. Do not rely on a failed create call.

## Body contract

A reviewer reads a short body. Agent-written bodies that claim changes the diff lacks lose reviewer trust.
When the repository tracks `.github/PULL_REQUEST_TEMPLATE.md`, use its section headings.
Otherwise use `## Why`, `## What changed`, `## How to verify`, and `## Risk`.
Keep the body file transient unless the repository tracks PR templates or release artifacts.
Leave a transient body file unstaged after verification.

Length and tone:

- Keep the body at 40 lines or fewer, not counting one diagram. Keep a small change at 20 lines or fewer.
- Give each prose section one to three sentences or bullets. Write `None` for an empty template section.
- Open with why in one or two sentences. A purpose that needs more than one sentence means a wrong topology. Decide it again.
- Do not restate the diff or list every file. When the change exceeds about 200 lines or 5 files, give a reading order.
- Use plain words. Do not use filler such as comprehensive, robust, seamless, leverage, significantly, or dramatically.
- Rewrite a supplied draft body. Keep only the facts that the evidence supports.

Claims:

- Name a change only when the net diff contains it. A reverted commit is not a change.
- List each verification as one line: the command and its result (`pass`, `fail`, or `not run`).
  List only checks that ran in this session. List a relevant check that did not run as `not run`.
  Never claim a benchmark, platform, harness, or speedup that no command measured.
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
