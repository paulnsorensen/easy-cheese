# diffray configuration

Custom [diffray](https://diffray.ai) code-review rules for easy-cheese, read by
the diffray GitHub App on every pull request.

## Layout

- `rules/*.md` — repo-specific review rules. Each file has YAML frontmatter
  (`name`, `description`, `patterns`, `agent`) followed by a prompt body.
  `patterns` are globs; a rule runs only when the PR touches a matching file.
  `agent` names the reviewer agent — built-ins are `general`, `security-scan`,
  `bug-hunter`, and `performance-check`.

diffray's built-in security, bug, and performance agents run on every PR
regardless; the rules here layer easy-cheese-specific conventions on top.

## Adding a rule

Drop a new `rules/<name>.md` file following the frontmatter shape above. To
define a custom reviewer agent, add `agents/<name>.md` (frontmatter: `name`,
`description`, `enabled`) and reference it from a rule's `agent` field.
