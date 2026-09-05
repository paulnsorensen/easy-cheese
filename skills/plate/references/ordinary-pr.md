# Ordinary PR publication

Use this path only after the final writing gate, the green quality gate, named-file
staging, the commit, and the commit verification.

## New PR

1. Confirm that `/plate` resolved the new PR as single. Accept an explicit choice, cohesive-shape inference, or a user answer.
2. Resolve the trunk and current branch. Reject publication from the trunk.
3. Draft a title and body. Include the purpose, non-obvious changes, verification, durable artifacts, and residual risks.
4. Write the body to a temporary or transient file. Pass that file through `--body-file`.
   Do not embed a markdown heredoc in `--body`.
5. Push the named branch without force.
6. Create the PR with an explicit base and head:

   ```bash
   gh pr create --title "<title>" --body-file <body-path> --base <base> --head <head>
   ```

7. Verify with `gh pr view --json number,url,title,baseRefName,headRefName,state`.

Do not use `--fill` when it would omit artifact or verification details.

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
  and merge remain `/gh`.

Query the current head for an existing PR before creation.
If a PR exists, switch to the existing-PR path. Do not rely on a failed create call.

## Body contract

Record the purpose, user-visible behavior, gate results, durable artifact rows, risks, follow-ups, and stack relationships.
Keep the body file transient unless the repository tracks PR templates or release artifacts.
Leave a transient body file unstaged after verification.

Write for the reviewer's verification pass:

- A semantics-preserving change says so in its first line. It names the mechanism and states the invariant to verify.
  Examples include a behavior-preserving refactor, an internal move, an internal rename, or a formatting-only change.
  Verify unchanged behavior. Add a mechanism-specific check. For example, verify that a move drops nothing and duplicates nothing.
  This check tells the reviewer to scan for accidental semantic drift. The reviewer does not infer intent line by line.
- A semantics-altering change names the changed behavior or contract. It also names its observable verification.
  This information directs scrutiny to the changed logic.
- A change that is not self-contained links its context. Link the spike branch, plan, or stack siblings that show the abstraction in use.
- A `## Non-obvious changes` section names every hunk whose intent is not visible from the diff alone, with one line of reason each.
  Write `None` when every hunk is self-evident. Author-annotated reviews carry markedly lower defect density (Cisco review data; see `.hallouminate/wiki/research/language-reviewability-evidence.md`).

## Push verification

Read the remote and upstream before pushing. Push the exact named head branch.
Verify local status. Verify the PR head and base.
A successful CLI exit without a matching PR head SHA is incomplete.
