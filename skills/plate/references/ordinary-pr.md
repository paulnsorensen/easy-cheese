# Ordinary PR publication

Use this path only after the final writing gate, green project gate, named-file
staging, commit, and commit verification.

## New PR

1. Confirm `/plate` resolved the new PR as single: explicitly, by cohesive-shape inference, or after a user question.
2. Resolve trunk and current branch; reject publication from trunk.
3. Draft a title and body covering purpose, verification, durable artifacts,
   and residual risks.
4. Write the body to a temporary or transient file and pass `--body-file`.
5. Push the named branch without force.
6. Create with explicit base and head:

```bash
gh pr create --title "<title>" --body-file <body-path> --base <base> --head <head>
```

1. Verify with `gh pr view --json number,url,title,baseRefName,headRefName,state`.

Do not use `--fill` when it would omit artifact or verification details.

## Existing ordinary PR

Do not ask the layout question. Read its base/head with `gh pr view`, commit the
validated named files, push the exact head branch, then read the PR back. Update
title/body only when the new work makes existing metadata inaccurate.

## Failures

Authentication or permission failures halt publication with the exact command
and error. A rejected push is not permission to force-push: fetch and explain
the divergence. Never create a duplicate PR when one already exists.
## Metadata and lifecycle

Publication-relevant GitHub operations remain here:

- Add `--draft` when explicitly requested.
- Add `--reviewer <login>` or `--assignee <login>` only from supplied
  publication metadata.
- Use `gh pr edit <number> --title <title> --body-file <path>` when verified
  commits make existing metadata inaccurate.
- Use `gh pr ready <number>` only when asked to publish a draft.
- `gh pr checks` may verify publication context; CI triage, review, comments,
  and merge remain `/gh`.

Query the current head for an existing PR before creation. If found, switch to
the existing-PR path rather than relying on a failed create call.

## Body contract

Record purpose, user-visible behavior, test/gate results, durable artifact
completion rows, risks, follow-ups, and any stack relationship. Keep the body
file transient unless the repo explicitly tracks PR templates or release
artifacts; leave it unstaged after verification.

## Push verification

Read remote/upstream before pushing. Push the exact named head branch. Verify
local status and the PR's head/base. A successful CLI exit without a matching PR
head SHA is incomplete.
